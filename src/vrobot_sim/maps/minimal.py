"""Minimal straight-then-right-angle map for numeric self-checks."""

from __future__ import annotations

from typing import Final

from vrobot_sim.map_model import EdgeDirection, MapEdge, MapNode, TopologyMap, build_topology_map

MINIMAL_MAP_ID: Final = "minimal"

# Integer coordinates keep the expected speed profile and trajectory endpoints analytic.
_MINIMAL_NODES = (
    MapNode("N01", 0.0, 0.0),
    MapNode("N02", 10.0, 0.0),
    MapNode("N03", 10.0, 5.0),
)

_MINIMAL_EDGES = (
    MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),
    MapEdge("E02", "N02", "N03", EdgeDirection.BOTH),
)

MINIMAL_MAP: Final[TopologyMap] = build_topology_map(MINIMAL_MAP_ID, _MINIMAL_NODES, _MINIMAL_EDGES)
