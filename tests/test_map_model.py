"""Build-time validation and derived-index tests for the topology map data model."""

from __future__ import annotations

import math

import pytest
from conftest import ASSERT_TOL

from vrobot_sim.map_model import (
    EdgeDirection,
    MapBuildError,
    MapCriticalZone,
    MapEdge,
    MapNode,
    MixedTrafficClass,
    build_topology_map,
)
from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID

MINIMAL_NODES = (
    MapNode("N01", 0.0, 0.0),
    MapNode("N02", 10.0, 0.0),
)
MINIMAL_EDGES = (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),)


def _build(edges, nodes=MINIMAL_NODES, zones=()):
    return build_topology_map("under_test", nodes, edges, zones)


def _find_cycle(map_obj):
    """Find a simple cycle of at least three distinct edges, or None."""
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for (from_id, to_id), edge in map_obj.edge_by_node_pair.items():
        adjacency.setdefault(from_id, []).append((to_id, edge.edge_id))

    def walk(node_id: str, path: list[str], edge_ids: frozenset[str]):
        for neighbour, edge_id in sorted(adjacency.get(node_id, ())):
            if edge_id in edge_ids:
                continue
            if neighbour == path[0]:
                if len(path) >= 3:
                    return path
                continue
            if neighbour in path:
                continue
            found = walk(neighbour, [*path, neighbour], edge_ids | {edge_id})
            if found is not None:
                return found
        return None

    for start in sorted(adjacency):
        found = walk(start, [start], frozenset())
        if found is not None:
            return found
    return None


def test_builtin_map_ids_are_the_only_loaded_maps():
    assert {load_map(MINIMAL_MAP_ID).map_id, load_map(DEMO_MAP_ID).map_id} == {"minimal", "demo"}


@pytest.mark.parametrize("map_id", [MINIMAL_MAP_ID, DEMO_MAP_ID])
def test_every_edge_exposes_all_five_attributes(map_id):
    map_obj = load_map(map_id)
    for edge in map_obj.edges:
        assert isinstance(edge.direction, EdgeDirection)
        assert isinstance(edge.lane_width_m, float)
        assert isinstance(edge.vehicle_classes, frozenset)
        assert isinstance(edge.cost_slope_percent, float)
        assert isinstance(edge.cost_mixed_traffic, MixedTrafficClass)


@pytest.mark.parametrize("map_id", [MINIMAL_MAP_ID, DEMO_MAP_ID])
def test_distance_cost_is_the_derived_geometric_length(map_id):
    map_obj = load_map(map_id)
    for edge in map_obj.edges:
        start = map_obj.node(edge.from_node_id)
        target = map_obj.node(edge.to_node_id)
        expected = math.hypot(target.x - start.x, target.y - start.y)
        assert map_obj.edge_length_m[edge.edge_id] == pytest.approx(expected, abs=ASSERT_TOL)


def test_critical_zone_members_all_resolve_in_the_same_map():
    for map_id in (MINIMAL_MAP_ID, DEMO_MAP_ID):
        map_obj = load_map(map_id)
        edge_ids = {edge.edge_id for edge in map_obj.edges}
        for zone in map_obj.zones:
            assert set(zone.edge_ids) <= edge_ids
            assert zone.capacity >= 1


@pytest.mark.parametrize("map_id", [MINIMAL_MAP_ID, DEMO_MAP_ID])
def test_edge_zones_inverts_the_zone_member_lists(map_id):
    map_obj = load_map(map_id)
    expected: dict[str, list[str]] = {}
    for zone in map_obj.zones:
        for edge_id in zone.edge_ids:
            expected.setdefault(edge_id, []).append(zone.zone_id)
    assert {edge_id: list(owners) for edge_id, owners in map_obj.edge_zones.items()} == {
        edge_id: sorted(owners) for edge_id, owners in expected.items()
    }


def test_demo_map_has_ten_startable_nodes_more_than_a_body_diameter_apart():
    map_obj = load_map(DEMO_MAP_ID)
    startable = {edge.from_node_id for edge in map_obj.edges} | {edge.to_node_id for edge in map_obj.edges}
    assert len(startable) >= 10

    nodes = [map_obj.node(node_id) for node_id in sorted(startable)]
    for index, first in enumerate(nodes):
        for second in nodes[index + 1:]:
            distance = math.hypot(second.x - first.x, second.y - first.y)
            assert distance > 0.70, f"start nodes {first.node_id} and {second.node_id} are {distance} m apart"


def test_minimal_map_has_no_zones_and_two_bidirectional_edges():
    map_obj = load_map(MINIMAL_MAP_ID)
    assert map_obj.zones == ()
    assert [edge.edge_id for edge in map_obj.edges] == ["E01", "E02"]
    assert all(edge.direction is EdgeDirection.BOTH for edge in map_obj.edges)
    assert map_obj.edge_length_m["E01"] == 10.0
    assert map_obj.edge_length_m["E02"] == 5.0
    assert map_obj.edge_by_node_pair[("N02", "N01")].edge_id == "E01"


def test_demo_map_ring_is_covered_by_mutually_exclusive_zones():
    map_obj = load_map(DEMO_MAP_ID)
    ring = _find_cycle(map_obj)
    assert ring is not None, "demo map must contain a cycle of at least three edges"
    assert len(ring) >= 3

    ring_edge_ids = [map_obj.edge_by_node_pair[(ring[i], ring[(i + 1) % len(ring)])].edge_id
                     for i in range(len(ring))]
    assert len(set(ring_edge_ids)) == len(ring_edge_ids)

    zones_by_edge = {edge_id: [zone.zone_id for zone in map_obj.zones if edge_id in zone.edge_ids]
                     for edge_id in ring_edge_ids}
    for edge_id, owners in zones_by_edge.items():
        assert len(owners) == 1, f"ring edge {edge_id} is not in exactly one zone"
    assert len({owners[0] for owners in zones_by_edge.values()}) == len(ring_edge_ids)


def test_demo_map_covers_one_way_edge_and_non_default_placeholder_attributes():
    map_obj = load_map(DEMO_MAP_ID)
    assert any(edge.direction is EdgeDirection.FWD for edge in map_obj.edges)
    assert any(
        edge.lane_width_m != 2.0
        and edge.cost_slope_percent != 0.0
        and edge.cost_mixed_traffic is not MixedTrafficClass.NONE
        for edge in map_obj.edges
    )
    assert len(map_obj.zones) >= 1
    shared = [
        edge_id
        for edge_id in (edge.edge_id for edge in map_obj.edges)
        if sum(1 for zone in map_obj.zones if edge_id in zone.edge_ids) > 1
    ]
    assert shared, "demo map must contain an edge claimed by more than one critical zone"


def test_duplicate_identifier_fails_and_names_the_object():
    with pytest.raises(MapBuildError) as excinfo:
        build_topology_map(
            "under_test",
            (MapNode("N01", 0.0, 0.0), MapNode("N01", 1.0, 0.0)),
            MINIMAL_EDGES,
        )
    assert "duplicate node id N01" in str(excinfo.value)

    with pytest.raises(MapBuildError) as excinfo:
        _build((MapEdge("E01", "N01", "N02", EdgeDirection.BOTH), MapEdge("E01", "N02", "N01", EdgeDirection.FWD)))
    assert "duplicate edge id E01" in str(excinfo.value)

    with pytest.raises(MapBuildError) as excinfo:
        _build(MINIMAL_EDGES, zones=(MapCriticalZone("Z01", "a", ("E01",)), MapCriticalZone("Z01", "b", ("E01",))))
    assert "duplicate critical zone id Z01" in str(excinfo.value)


def test_parallel_edge_on_the_same_ordered_node_pair_is_rejected():
    with pytest.raises(MapBuildError) as excinfo:
        _build(
            (
                MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),
                MapEdge("E02", "N01", "N02", EdgeDirection.FWD),
            )
        )
    assert "('N01', 'N02')" in str(excinfo.value)
    assert "E02" in str(excinfo.value)


def test_both_edge_and_reverse_one_way_edge_competing_for_a_pair_are_rejected():
    """A BOTH edge already claims the reverse pair, so a reverse FWD edge is a parallel edge."""
    with pytest.raises(MapBuildError) as excinfo:
        _build(
            (
                MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),
                MapEdge("E02", "N02", "N01", EdgeDirection.FWD),
            )
        )
    message = str(excinfo.value)
    assert "('N02', 'N01')" in message
    assert "E01" in message and "E02" in message


def test_two_both_edges_between_the_same_nodes_are_rejected():
    with pytest.raises(MapBuildError) as excinfo:
        _build(
            (
                MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),
                MapEdge("E02", "N02", "N01", EdgeDirection.BOTH),
            )
        )
    assert "share ordered node pair" in str(excinfo.value)


def test_edge_between_coincident_nodes_fails_the_build_instead_of_dividing_by_zero():
    with pytest.raises(MapBuildError) as excinfo:
        build_topology_map(
            "under_test",
            (MapNode("N01", 3.0, 4.0), MapNode("N02", 3.0, 4.0)),
            (MapEdge("E07", "N01", "N02", EdgeDirection.BOTH),),
        )
    message = str(excinfo.value)
    assert "E07" in message
    assert "zero length" in message


def test_edge_with_unknown_endpoint_is_rejected_and_names_the_edge():
    with pytest.raises(MapBuildError) as excinfo:
        _build((MapEdge("E09", "N01", "NOPE", EdgeDirection.BOTH),))
    message = str(excinfo.value)
    assert "E09" in message
    assert "to_node_id=NOPE" in message


def test_critical_zone_member_edge_that_does_not_exist_is_rejected():
    with pytest.raises(MapBuildError) as excinfo:
        _build(MINIMAL_EDGES, zones=(MapCriticalZone("Z01", "ghost", ("E404",)),))
    message = str(excinfo.value)
    assert "Z01" in message
    assert "E404" in message


def test_out_of_range_numeric_fields_are_rejected():
    with pytest.raises(MapBuildError) as excinfo:
        _build(
            (
                MapEdge("E01", "N01", "N02", EdgeDirection.BOTH, lane_width_m=0.5),
                MapEdge("E02", "N02", "N01", EdgeDirection.FWD, cost_slope_percent=-40.0),
            ),
            zones=(MapCriticalZone("Z01", "a", ("E01",), capacity=0),),
        )
    message = str(excinfo.value)
    assert "lane_width_m=0.5" in message
    assert "cost_slope_percent=-40.0" in message
    assert "capacity=0" in message

    with pytest.raises(MapBuildError) as excinfo:
        build_topology_map("under_test", (MapNode("N01", 0.0, 400.0), MapNode("N02", 1.0, 0.0)), MINIMAL_EDGES)
    assert "node N01 field y=400.0" in str(excinfo.value)


def test_derived_indexes_are_read_only():
    map_obj = load_map(MINIMAL_MAP_ID)
    with pytest.raises(TypeError):
        map_obj.edge_length_m["E01"] = 1.0
    with pytest.raises(TypeError):
        map_obj.edge_by_node_pair[("N01", "N02")] = map_obj.edges[0]
    demo_map = load_map(DEMO_MAP_ID)
    with pytest.raises(TypeError):
        demo_map.edge_zones["E01"] = ()


def test_all_violations_are_reported_together():
    with pytest.raises(MapBuildError) as excinfo:
        build_topology_map(
            "under_test",
            (MapNode("N01", 0.0, 0.0), MapNode("N01", 0.0, 999.0)),
            (MapEdge("E01", "N01", "MISSING", EdgeDirection.BOTH, lane_width_m=9.0),),
        )
    assert len(excinfo.value.violations) == 4
