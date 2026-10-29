"""Demo map through the kernel: build-time validity and the shapes WI-mutex-scheduling needs."""

from __future__ import annotations

import pytest
from conftest import DT_S, make_spec

from vrobot_sim.map_model import EdgeDirection, MixedTrafficClass, build_topology_map
from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.robot import RobotStatus
from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation

LEGAL_PATHS = (
    ("N01", "N02", "N03", "N01"),
    ("N04", "N05", "N06", "N07"),
    ("N02", "N03", "N01"),
)


def _demo_scenario() -> Scenario:
    specs = tuple(
        make_spec(
            robot_id=f"R{index}",
            path=path,
            start_node_id=path[0],
            start_theta_rad=0.0 if path[0] == "N01" else 0.5,
        )
        for index, path in enumerate(LEGAL_PATHS, start=1)
    )
    return Scenario(map_id=DEMO_MAP_ID, dt_s=DT_S, robots=specs)


def test_the_demo_map_passes_build_and_creation_validation():
    map_obj = load_map(DEMO_MAP_ID)
    assert map_obj.map_id == DEMO_MAP_ID
    assert len(map_obj.nodes) == 10
    assert len(map_obj.edges) == 11
    assert len(map_obj.zones) == 5

    sim = Simulation.create(_demo_scenario())
    snapshot = sim.step()
    assert [item.robot_id for item in snapshot.robots] == ["R1", "R2", "R3"]
    assert all(item.status is RobotStatus.MOVING for item in snapshot.robots)


def test_the_ring_legs_belong_to_mutually_exclusive_zones_with_a_shared_branch_edge():
    map_obj = load_map(DEMO_MAP_ID)
    owners = {
        edge_id: [zone.zone_id for zone in map_obj.zones if edge_id in zone.edge_ids]
        for edge_id in ("E01", "E02", "E03")
    }
    assert [owners["E01"], owners["E02"], owners["E03"]] == [["Z01"], ["Z02"], ["Z03"]]
    assert all(zone.capacity == 1 for zone in map_obj.zones)
    assert len(map_obj.edge_by_node_pair[("N01", "N02")].edge_id) > 0

    shared = [edge_id for edge_id in ("E04", "E05", "E06", "E07") if len(
        [zone for zone in map_obj.zones if edge_id in zone.edge_ids]
    ) > 1]
    assert shared == ["E05"]


def test_the_map_keeps_a_one_way_edge_and_non_default_placeholder_attributes():
    map_obj = load_map(DEMO_MAP_ID)
    one_way = [edge for edge in map_obj.edges if edge.direction is EdgeDirection.FWD]
    assert [edge.edge_id for edge in one_way] == ["E02"]
    assert map_obj.edge_by_node_pair.get(("N03", "N02")) is None
    assert map_obj.edge_by_node_pair.get(("N02", "N03")) is one_way[0]

    annotated = [edge for edge in map_obj.edges if edge.lane_width_m != 2.0]
    assert len(annotated) == 1
    assert annotated[0].cost_slope_percent == 6.0
    assert annotated[0].cost_mixed_traffic is MixedTrafficClass.MID
    assert annotated[0].vehicle_classes == frozenset({"AMR-500", "AMR-1000"})


def test_robots_move_on_their_legal_demo_paths_without_multi_robot_assertions():
    sim = Simulation.create(_demo_scenario())
    start = {item.robot_id: (item.x_m, item.y_m) for item in sim.step().robots}
    assert set(start) == {"R1", "R2", "R3"}

    for _ in range(200):
        snapshot = sim.step()
    final = {item.robot_id: (item.x_m, item.y_m) for item in snapshot.robots}
    assert all(final[robot_id] != start[robot_id] for robot_id in start)
    assert all(item.status in {RobotStatus.MOVING, RobotStatus.ARRIVED} for item in snapshot.robots)


def test_a_path_fighting_a_one_way_edge_is_refused_and_the_robot_stays_idle():
    spec = make_spec(robot_id="R9", path=("N03", "N02"), start_node_id="N03")
    sim = Simulation.create(Scenario(map_id=DEMO_MAP_ID, dt_s=DT_S, robots=(spec,)))
    snapshot = sim.step()
    assert snapshot.robots[0].status is RobotStatus.IDLE
    assert (snapshot.robots[0].x_m, snapshot.robots[0].y_m) == (10.0, 15.0)

    for _ in range(50):
        snapshot = sim.step()
    assert snapshot.robots[0].status is RobotStatus.IDLE
    assert snapshot.robots[0].v_mps == 0.0


def test_a_critical_zone_membership_that_is_not_in_the_map_fails_the_build():
    from vrobot_sim.map_model import MapBuildError, MapCriticalZone, MapEdge, MapNode

    with pytest.raises(MapBuildError):
        build_topology_map(
            "demo_variant",
            (MapNode("N01", 0.0, 0.0), MapNode("N02", 1.0, 0.0)),
            (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),),
            (MapCriticalZone("Z09", "phantom member", ("E404",)),),
        )
