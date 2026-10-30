"""Scene configuration, anchor validation and node-path derivation.

The browser sends anchors (start, ordered waypoints, target); this module turns them into
the full node path the kernel needs, choosing the shortest route that respects one-way
edges. Every violation is collected before any object is built.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

from pydantic import BaseModel, Field

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.robot import ChassisConfig, RobotSpec
from vrobot_sim.scenario import Scenario

SCENE_DT_S = 0.02
MIN_ROBOTS = 1
MAX_ROBOTS = 10
VEHICLE_CLASS = "AMR-500"


class RobotConfig(BaseModel):
    """One robot's anchors as submitted by the browser."""

    robot_id: str
    start_node_id: str
    waypoints: list[str] = Field(default_factory=list)
    target_node_id: str


class SceneConfig(BaseModel):
    """The browser-submitted scene. Map choice is fixed to ``demo``."""

    robots: list[RobotConfig] = Field(default_factory=list)


class SceneResolutionError(ValueError):
    """Raised with every violation at once; no simulation is built."""

    def __init__(self, violations: Sequence[str]):
        self.violations = tuple(violations)
        super().__init__("scene resolution failed: " + "; ".join(self.violations))


@dataclass(frozen=True)
class ResolvedScene:
    """A validated scenario plus the full node path derived for each robot."""

    scenario: Scenario
    paths: Mapping[str, tuple[str, ...]]


def resolve_scene(config: SceneConfig, topology_map: TopologyMap | None = None) -> ResolvedScene:
    """Validate every robot, derive its node path and build the kernel scenario.

    ``topology_map`` defaults to the built-in demo map; callers validating another map
    pass it explicitly.
    """
    topology = topology_map if topology_map is not None else load_map(DEMO_MAP_ID)
    violations: list[str] = []
    _check_count(len(config.robots), violations)

    known_nodes = {node.node_id for node in topology.nodes}
    adjacency = _adjacency(topology)
    seen_robot_ids: set[str] = set()
    seen_starts: set[str] = set()
    specs: list[RobotSpec] = []
    paths: dict[str, tuple[str, ...]] = {}

    for robot in config.robots:
        _check_identity(robot, violations, seen_robot_ids, seen_starts)
        anchors = [robot.start_node_id, *robot.waypoints, robot.target_node_id]
        _check_anchors(robot, anchors, known_nodes, topology, violations)
        if any(node not in known_nodes for node in anchors):
            continue
        path = _anchor_path(robot.robot_id, anchors, adjacency, violations)
        if path is None:
            continue
        paths[robot.robot_id] = tuple(path)
        specs.append(_robot_spec(robot, path, topology))

    if violations:
        raise SceneResolutionError(violations)
    scenario = Scenario(map_id=topology.map_id, dt_s=SCENE_DT_S, robots=tuple(specs))
    return ResolvedScene(scenario=scenario, paths=paths)


def _check_count(count: int, violations: list[str]) -> None:
    if not MIN_ROBOTS <= count <= MAX_ROBOTS:
        violations.append(f"robot count {count} is outside {MIN_ROBOTS}-{MAX_ROBOTS}")


def _check_identity(
    robot: RobotConfig,
    violations: list[str],
    seen_ids: set[str],
    seen_starts: set[str],
) -> None:
    if robot.robot_id in seen_ids:
        violations.append(f"duplicate robot_id {robot.robot_id!r}")
    seen_ids.add(robot.robot_id)
    if robot.start_node_id in seen_starts:
        violations.append(f"robot {robot.robot_id} shares start node {robot.start_node_id} with an earlier robot")
    seen_starts.add(robot.start_node_id)


def _check_anchors(
    robot: RobotConfig,
    anchors: list[str],
    known_nodes: set[str],
    topology: TopologyMap,
    violations: list[str],
) -> None:
    for node_id in dict.fromkeys(anchors):
        if node_id not in known_nodes:
            violations.append(f"robot {robot.robot_id} anchor {node_id} is not in map {topology.map_id}")
    if robot.start_node_id == robot.target_node_id:
        violations.append(
            f"robot {robot.robot_id} start_node_id equals target_node_id {robot.target_node_id}"
        )
    for from_id, to_id in zip(anchors, anchors[1:]):
        if from_id == to_id:
            violations.append(f"robot {robot.robot_id} anchor chain repeats node {from_id}")


def _anchor_path(
    robot_id: str,
    anchors: list[str],
    adjacency: Mapping[str, tuple[str, ...]],
    violations: list[str],
) -> list[str] | None:
    """Join one shortest route per anchor pair; every unreachable pair is reported."""
    segments: list[list[str]] = []
    for from_id, to_id in zip(anchors, anchors[1:]):
        segment = _shortest_path(adjacency, from_id, to_id)
        if segment is None:
            violations.append(f"robot {robot_id} has no route from {from_id} to {to_id}")
        else:
            segments.append(segment)
    if len(segments) != len(anchors) - 1:
        return None
    path = list(segments[0])
    for segment in segments[1:]:
        path.extend(segment[1:])
    return path


def _adjacency(topology: TopologyMap) -> dict[str, tuple[str, ...]]:
    """Directed neighbours from the traversable pair index, sorted for determinism."""
    neighbours: dict[str, list[str]] = {}
    for from_id, to_id in topology.edge_by_node_pair:
        neighbours.setdefault(from_id, []).append(to_id)
    return {node_id: tuple(sorted(set(targets))) for node_id, targets in neighbours.items()}


def _shortest_path(
    adjacency: Mapping[str, tuple[str, ...]], start: str, target: str
) -> list[str] | None:
    """BFS over traversable directions; ties resolve by ascending node id."""
    if start == target:
        return [start]
    parents: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if node == target:
            break
        for neighbour in adjacency.get(node, ()):
            if neighbour not in parents:
                parents[neighbour] = node
                queue.append(neighbour)
    if target not in parents:
        return None
    path = [target]
    while parents[path[-1]] is not None:
        path.append(parents[path[-1]])
    return path[::-1]


def _robot_spec(robot: RobotConfig, path: list[str], topology: TopologyMap) -> RobotSpec:
    heading = (
        topology.segment_geometry(path[0], path[1]).heading_rad if len(path) >= 2 else 0.0
    )
    return RobotSpec(
        robot_id=robot.robot_id,
        chassis=ChassisConfig(),
        vehicle_class=VEHICLE_CLASS,
        start_node_id=robot.start_node_id,
        start_theta_rad=heading,
        planned_node_path=tuple(path),
    )
