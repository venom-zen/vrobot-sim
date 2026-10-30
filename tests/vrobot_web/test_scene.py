"""Scene validation, anchor routing and kernel assembly tests."""

from __future__ import annotations

import math

import pytest
from vrobot_sim.map_model import EdgeDirection, MapEdge, MapNode, build_topology_map
from vrobot_sim.maps.demo import DEMO_MAP
from vrobot_sim.simulation import Simulation

from vrobot_web.scene import (
    RobotConfig,
    SceneConfig,
    SceneResolutionError,
    resolve_scene,
)

# Two nodes joined in the only traversable direction, plus an isolated third node.
PARTIAL_MAP = build_topology_map(
    "partial",
    (MapNode("N01", 0.0, 0.0), MapNode("N02", 20.0, 0.0), MapNode("N03", 40.0, 0.0)),
    (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),),
)


def _robot(
    robot_id: str = "R1",
    start: str = "N01",
    waypoints: list[str] | None = None,
    target: str = "N03",
) -> RobotConfig:
    return RobotConfig(
        robot_id=robot_id,
        start_node_id=start,
        waypoints=waypoints or [],
        target_node_id=target,
    )


def _resolve(*robots: RobotConfig, topology=DEMO_MAP):
    return resolve_scene(SceneConfig(robots=list(robots)), topology)


def _violations(*robots: RobotConfig, topology=DEMO_MAP) -> tuple[str, ...]:
    with pytest.raises(SceneResolutionError) as caught:
        _resolve(*robots, topology=topology)
    return caught.value.violations


def test_unreachable_route_and_duplicate_start_are_reported_together():
    violations = _violations(
        _robot("R1", "N01", target="N02"),
        _robot("R2", "N01", target="N03"),
        topology=PARTIAL_MAP,
    )
    assert any("shares start node N01" in message for message in violations)
    assert any("R2 has no route from N01 to N03" in message for message in violations)


def test_direct_target_uses_the_bidirectional_ring_edge():
    resolved = _resolve(_robot("R1", "N01", target="N03"))
    assert resolved.paths["R1"] == ("N01", "N03")


def test_waypoints_are_visited_in_order_with_shortest_segments():
    resolved = _resolve(_robot("R1", "N01", waypoints=["N02"], target="N03"))
    assert resolved.paths["R1"] == ("N01", "N02", "N03")


def test_multiple_waypoints_join_every_segment_in_order():
    resolved = _resolve(_robot("R1", "N01", waypoints=["N08", "N10"], target="N09"))
    assert resolved.paths["R1"] == ("N01", "N08", "N10", "N09")


def test_one_way_edge_forces_a_detour():
    resolved = _resolve(_robot("R1", "N03", target="N02"))
    assert resolved.paths["R1"] == ("N03", "N01", "N02")


def test_ring_deadlock_configuration_derives_the_three_ring_paths():
    resolved = _resolve(
        _robot("R1", "N01", waypoints=["N02"], target="N03"),
        _robot("R2", "N02", waypoints=["N03"], target="N01"),
        _robot("R3", "N03", waypoints=["N01"], target="N02"),
    )
    assert resolved.paths == {
        "R1": ("N01", "N02", "N03"),
        "R2": ("N02", "N03", "N01"),
        "R3": ("N03", "N01", "N02"),
    }


def test_start_heading_follows_the_first_segment():
    resolved = _resolve(_robot("R1", "N03", target="N02"))
    spec = resolved.scenario.robots[0]
    assert spec.start_theta_rad == pytest.approx(math.atan2(-15.0, -10.0))


def test_ten_robots_build_a_kernel_that_steps():
    starts = {
        "R01": ("N01", "N02"),
        "R02": ("N02", "N03"),
        "R03": ("N03", "N01"),
        "R04": ("N04", "N02"),
        "R05": ("N05", "N04"),
        "R06": ("N06", "N05"),
        "R07": ("N07", "N06"),
        "R08": ("N08", "N01"),
        "R09": ("N09", "N07"),
        "R10": ("N10", "N08"),
    }
    resolved = _resolve(
        *[_robot(robot_id, start, target=target) for robot_id, (start, target) in starts.items()]
    )
    assert len(resolved.scenario.robots) == 10
    snapshot = Simulation.create_scheduled(resolved.scenario).step()
    assert snapshot.tick_index == 0
    assert [robot.robot_id for robot in snapshot.robots] == sorted(starts)


def test_duplicate_robot_ids_are_rejected():
    violations = _violations(
        _robot("R1", "N01", target="N02"),
        _robot("R1", "N03", target="N01"),
    )
    assert any("duplicate robot_id 'R1'" in message for message in violations)


def test_robot_count_outside_the_supported_range_is_rejected():
    assert any("robot count 0 is outside 1-10" in message for message in _violations())
    eleven = [_robot(f"R{index}", "N01", target="N02") for index in range(11)]
    violations = _violations(*eleven)
    assert any("robot count 11 is outside 1-10" in message for message in violations)


def test_start_equal_to_target_is_rejected():
    violations = _violations(_robot("R1", "N01", target="N01"))
    assert any("start_node_id equals target_node_id N01" in message for message in violations)


def test_repeated_anchor_in_chain_is_rejected():
    violations = _violations(_robot("R1", "N01", waypoints=["N01"], target="N03"))
    assert any("anchor chain repeats node N01" in message for message in violations)


def test_anchor_outside_the_map_is_rejected():
    violations = _violations(_robot("R1", "N99", target="N03"))
    assert any("anchor N99 is not in map demo" in message for message in violations)


def test_every_unreachable_segment_is_listed():
    violations = _violations(
        _robot("R1", "N01", waypoints=["N03"], target="N02"),
        topology=PARTIAL_MAP,
    )
    unreachable = [message for message in violations if "has no route" in message]
    assert len(unreachable) == 2
