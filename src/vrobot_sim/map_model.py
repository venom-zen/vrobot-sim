"""Topology map data objects, build-time validation and derived indexes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

VEHICLE_CLASS_TAGS = frozenset({"AMR-500", "AMR-1000", "FORK"})

NODE_COORDINATE_RANGE = (0.0, 200.0)
LANE_WIDTH_RANGE = (1.0, 6.0)
COST_SLOPE_RANGE = (-15.0, 15.0)
DEFAULT_LANE_WIDTH_M = 2.0

MINIMUM_CRITICAL_ZONE_CAPACITY = 1
MINIMUM_ZONE_EDGE_COUNT = 1


class EdgeDirection(Enum):
    """Traversal allowance for an edge; reverse-only travel swaps the endpoints."""

    FWD = "fwd"
    BOTH = "both"


class MixedTrafficClass(Enum):
    """Pedestrian-mixing cost class. Not consumed by this work item."""

    NONE = "none"
    LOW = "low"
    MID = "mid"
    HIGH = "high"


@dataclass(frozen=True)
class MapNode:
    node_id: str
    x: float
    y: float


@dataclass(frozen=True)
class MapEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    direction: EdgeDirection
    lane_width_m: float = DEFAULT_LANE_WIDTH_M
    vehicle_classes: frozenset[str] = frozenset()
    cost_slope_percent: float = 0.0
    cost_mixed_traffic: MixedTrafficClass = MixedTrafficClass.NONE


@dataclass(frozen=True)
class MapCriticalZone:
    """The member edge list is the only source of the edge-to-zone relation."""

    zone_id: str
    name: str
    edge_ids: tuple[str, ...]
    capacity: int = 1


@dataclass(frozen=True)
class SegmentGeometry:
    """One traversed edge: the straight line a robot drives along."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    start_x: float
    start_y: float
    unit_x: float
    unit_y: float
    heading_rad: float
    length_m: float

    def arc_position(self, x: float, y: float) -> float:
        """Projection of a point on the segment line, measured from the segment start."""
        return (x - self.start_x) * self.unit_x + (y - self.start_y) * self.unit_y

    def perpendicular_offset(self, x: float, y: float) -> float:
        """Signed distance from the segment line; zero on the line itself."""
        return -(x - self.start_x) * self.unit_y + (y - self.start_y) * self.unit_x


class MapBuildError(ValueError):
    """Raised when map data fails build validation; no partial map escapes."""

    def __init__(self, violations: Sequence[str]):
        self.violations = tuple(violations)
        super().__init__("topology map build failed: " + "; ".join(self.violations))


@dataclass(frozen=True)
class TopologyMap:
    """Immutable map data plus the read-only indexes derived in one build call."""

    map_id: str
    nodes: tuple[MapNode, ...]
    edges: tuple[MapEdge, ...]
    zones: tuple[MapCriticalZone, ...]
    edge_length_m: Mapping[str, float]
    edge_by_node_pair: Mapping[tuple[str, str], MapEdge]
    edge_zones: Mapping[str, tuple[str, ...]]

    def node(self, node_id: str) -> MapNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def edge(self, edge_id: str) -> MapEdge:
        for edge in self.edges:
            if edge.edge_id == edge_id:
                return edge
        raise KeyError(edge_id)

    def segment_geometry(self, from_node_id: str, to_node_id: str) -> SegmentGeometry:
        edge = self.edge_by_node_pair[(from_node_id, to_node_id)]
        start = self.node(from_node_id)
        target = self.node(to_node_id)
        delta_x = target.x - start.x
        delta_y = target.y - start.y
        length = self.edge_length_m[edge.edge_id]
        return SegmentGeometry(
            edge_id=edge.edge_id,
            from_node_id=start.node_id,
            to_node_id=target.node_id,
            start_x=start.x,
            start_y=start.y,
            unit_x=delta_x / length,
            unit_y=delta_y / length,
            heading_rad=math.atan2(delta_y, delta_x),
            length_m=length,
        )


def _duplicate_ids(
    violations: list[str], kind: str, items: Sequence[Any], id_of: Callable[[Any], str]
) -> set[str]:
    unique: set[str] = set()
    for item in items:
        item_id = id_of(item)
        if item_id in unique:
            violations.append(f"duplicate {kind} id {item_id}")
        else:
            unique.add(item_id)
    return unique


def _check_node_ranges(violations: list[str], nodes: Sequence[MapNode]) -> None:
    low, high = NODE_COORDINATE_RANGE
    for node in nodes:
        for name, value in (("x", node.x), ("y", node.y)):
            if not low <= value <= high:
                violations.append(f"node {node.node_id} field {name}={value} outside [{low}, {high}]")


def _check_edge_endpoints(violations: list[str], edges: Sequence[MapEdge], node_ids: set[str]) -> None:
    for edge in edges:
        for role, node_id in (("from_node_id", edge.from_node_id), ("to_node_id", edge.to_node_id)):
            if node_id not in node_ids:
                violations.append(f"edge {edge.edge_id} field {role}={node_id} is not a map node")


def _check_edge_field_ranges(violations: list[str], edges: Sequence[MapEdge]) -> None:
    for edge in edges:
        low, high = LANE_WIDTH_RANGE
        if not low <= edge.lane_width_m <= high:
            violations.append(
                f"edge {edge.edge_id} field lane_width_m={edge.lane_width_m} outside [{low}, {high}]"
            )
        low, high = COST_SLOPE_RANGE
        if not low <= edge.cost_slope_percent <= high:
            violations.append(
                f"edge {edge.edge_id} field cost_slope_percent={edge.cost_slope_percent} "
                f"outside [{low}, {high}]"
            )
        unknown = edge.vehicle_classes - VEHICLE_CLASS_TAGS
        if unknown:
            violations.append(
                f"edge {edge.edge_id} field vehicle_classes has unknown tags {sorted(unknown)}"
            )


def _check_zone_membership(violations: list[str], zones: Sequence[MapCriticalZone], edge_ids: set[str]) -> None:
    for zone in zones:
        if len(zone.edge_ids) < MINIMUM_ZONE_EDGE_COUNT:
            violations.append(f"critical zone {zone.zone_id} field edge_ids has no member")
        for edge_id in zone.edge_ids:
            if edge_id not in edge_ids:
                violations.append(f"critical zone {zone.zone_id} member edge {edge_id} is not a map edge")
        if zone.capacity < MINIMUM_CRITICAL_ZONE_CAPACITY:
            violations.append(
                f"critical zone {zone.zone_id} field capacity={zone.capacity} "
                f"below {MINIMUM_CRITICAL_ZONE_CAPACITY}"
            )


def _effective_pairs(edge: MapEdge) -> tuple[tuple[str, str], ...]:
    """Every ordered node pair the edge makes traversable, which is what the index exposes."""
    forward = (edge.from_node_id, edge.to_node_id)
    if edge.direction is not EdgeDirection.BOTH:
        return (forward,)
    reverse = (edge.to_node_id, edge.from_node_id)
    return (forward,) if reverse == forward else (forward, reverse)


def _check_parallel_edges(violations: list[str], edges: Sequence[MapEdge]) -> None:
    first_owner: dict[tuple[str, str], str] = {}
    for edge in edges:
        for pair in _effective_pairs(edge):
            owner = first_owner.get(pair)
            if owner is None:
                first_owner[pair] = edge.edge_id
            else:
                violations.append(f"edges {owner} and {edge.edge_id} share ordered node pair {pair}")


def _check_edge_lengths(
    violations: list[str], edges: Sequence[MapEdge], node_by_id: Mapping[str, MapNode]
) -> None:
    for edge in edges:
        start = node_by_id.get(edge.from_node_id)
        target = node_by_id.get(edge.to_node_id)
        if start is None or target is None:
            continue
        if _edge_length(edge, node_by_id) == 0.0:
            violations.append(
                f"edge {edge.edge_id} has zero length: nodes {start.node_id} and {target.node_id} share coordinates"
            )


def _edge_length(edge: MapEdge, node_by_id: Mapping[str, MapNode]) -> float:
    start = node_by_id[edge.from_node_id]
    target = node_by_id[edge.to_node_id]
    return math.hypot(target.x - start.x, target.y - start.y)


def build_topology_map(
    map_id: str,
    nodes: Sequence[MapNode],
    edges: Sequence[MapEdge],
    zones: Sequence[MapCriticalZone] = (),
) -> TopologyMap:
    """Validate everything first, then return one immutable map with read-only derived indexes."""
    violations: list[str] = []
    node_by_id = {node.node_id: node for node in nodes}
    node_ids = _duplicate_ids(violations, "node", nodes, lambda item: item.node_id)
    edge_ids = _duplicate_ids(violations, "edge", edges, lambda item: item.edge_id)
    _duplicate_ids(violations, "critical zone", zones, lambda item: item.zone_id)
    _check_node_ranges(violations, nodes)
    _check_edge_endpoints(violations, edges, node_ids)
    _check_zone_membership(violations, zones, edge_ids)
    _check_parallel_edges(violations, edges)
    _check_edge_field_ranges(violations, edges)
    _check_edge_lengths(violations, edges, node_by_id)
    if violations:
        raise MapBuildError(violations)

    length_by_edge = {edge.edge_id: _edge_length(edge, node_by_id) for edge in edges}
    pair_index: dict[tuple[str, str], MapEdge] = {}
    for edge in edges:
        for pair in _effective_pairs(edge):
            pair_index[pair] = edge
    return TopologyMap(
        map_id=map_id,
        nodes=tuple(nodes),
        edges=tuple(edges),
        zones=tuple(zones),
        edge_length_m=MappingProxyType(length_by_edge),
        edge_by_node_pair=MappingProxyType(pair_index),
        edge_zones=MappingProxyType(_edge_zones_by_id(zones)),
    )


def _edge_zones_by_id(zones: Sequence[MapCriticalZone]) -> dict[str, tuple[str, ...]]:
    """Invert the zone member-edge lists so the relation keeps a single source."""
    owners_by_edge: dict[str, list[str]] = {}
    for zone in zones:
        for edge_id in zone.edge_ids:
            owners_by_edge.setdefault(edge_id, []).append(zone.zone_id)
    return {edge_id: tuple(sorted(zone_ids)) for edge_id, zone_ids in owners_by_edge.items()}
