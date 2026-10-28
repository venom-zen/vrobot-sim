"""Demo map: triangular ring with critical zones, branch and turn chain."""

from __future__ import annotations

from typing import Final

from vrobot_sim.map_model import (
    EdgeDirection,
    MapCriticalZone,
    MapEdge,
    MapNode,
    MixedTrafficClass,
    TopologyMap,
    build_topology_map,
)

DEMO_MAP_ID: Final = "demo"

_DEMO_NODES = (
    MapNode("N01", 0.0, 0.0),
    MapNode("N02", 20.0, 0.0),
    MapNode("N03", 10.0, 15.0),
    MapNode("N04", 20.0, 12.0),
    MapNode("N05", 20.0, 16.0),
    MapNode("N06", 16.0, 16.0),
    MapNode("N07", 16.0, 20.0),
)

# E01 carries the non-default placeholder attributes; E02 is the one-way edge that
# makes the ring dependency directed.
_DEMO_EDGES = (
    MapEdge(
        "E01",
        "N01",
        "N02",
        EdgeDirection.BOTH,
        lane_width_m=3.5,
        vehicle_classes=frozenset({"AMR-500", "AMR-1000"}),
        cost_slope_percent=6.0,
        cost_mixed_traffic=MixedTrafficClass.MID,
    ),
    MapEdge("E02", "N02", "N03", EdgeDirection.FWD),
    MapEdge("E03", "N03", "N01", EdgeDirection.BOTH),
    MapEdge("E04", "N02", "N04", EdgeDirection.BOTH),
    MapEdge("E05", "N04", "N05", EdgeDirection.BOTH),
    MapEdge("E06", "N05", "N06", EdgeDirection.BOTH),
    MapEdge("E07", "N06", "N07", EdgeDirection.BOTH),
)

# The three ring edges sit in mutually exclusive zones, which is the shape
# WI-mutex-scheduling needs for a circular wait. E05 belongs to two zones on purpose.
_DEMO_ZONES = (
    MapCriticalZone("Z01", "ring leg N01-N02", ("E01",), capacity=1),
    MapCriticalZone("Z02", "ring leg N02-N03", ("E02",), capacity=1),
    MapCriticalZone("Z03", "ring leg N03-N01", ("E03",), capacity=1),
    MapCriticalZone("Z04", "branch entrance", ("E04", "E05"), capacity=1),
    MapCriticalZone("Z05", "turn chain", ("E05", "E06", "E07"), capacity=1),
)

DEMO_MAP: Final[TopologyMap] = build_topology_map(DEMO_MAP_ID, _DEMO_NODES, _DEMO_EDGES, _DEMO_ZONES)
