"""Unit tests for the forward-looking safety window, the lateral gate and the obstacle field."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest
from conftest import (
    BODY_RADIUS_M,
    DECEL_MAX_MPS2,
    DT_S,
    V_MAX_MPS,
    make_obstacle_field,
    make_robot,
    make_spec,
    obstacle_at,
)

from vrobot_sim.kinematics import Pose
from vrobot_sim.map_model import TopologyMap
from vrobot_sim.maps import load_map
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.obstacle_field import Obstacle, ObstacleField, ObstacleRejection
from vrobot_sim.robot import ChassisConfig, CommandKind, EStopReason, MotionCommand, RobotStatus
from vrobot_sim.safety import SafetyMonitor

EDGE_LENGTH_M = 10.0
OBSTACLE_RADIUS_M = 0.2


@dataclass(frozen=True)
class _SpecView:
    chassis: ChassisConfig


@dataclass(frozen=True)
class _RobotView:
    """The read surface SafetyMonitor needs from a robot."""

    pose: Pose
    v_mps: float
    spec: _SpecView


def _robot(x: float = 0.0, y: float = 0.0, v_mps: float = V_MAX_MPS) -> _RobotView:
    return _RobotView(Pose(x, y, 0.0), v_mps, _SpecView(ChassisConfig()))


def _obstacle(center_x: float, center_y: float, radius_m: float = OBSTACLE_RADIUS_M) -> Obstacle:
    return Obstacle("OBS", center_x, center_y, radius_m)


def _segment(map_obj: TopologyMap | None = None, from_node: str = "N01", to_node: str = "N02"):
    return (map_obj or load_map(MINIMAL_MAP_ID)).segment_geometry(from_node, to_node)


def _lookahead_m(v_mps: float, dt: float = DT_S) -> float:
    return v_mps * v_mps / (2.0 * DECEL_MAX_MPS2) + BODY_RADIUS_M + v_mps * dt


def test_no_obstacles_means_no_request():
    assert SafetyMonitor().check(_robot(), (), _segment(), DT_S) is EStopReason.NONE


def test_obstacle_ahead_inside_the_lookahead_window_triggers():
    request = SafetyMonitor().check(_robot(), (_obstacle(1.0, 0.0),), _segment(), DT_S)
    assert request is EStopReason.SAFETY_DISTANCE


def test_obstacle_ahead_beyond_the_lookahead_window_does_not_trigger():
    assert SafetyMonitor().check(_robot(), (_obstacle(5.0, 0.0),), _segment(), DT_S) is EStopReason.NONE


def test_lateral_obstacle_outside_the_clearance_is_skipped():
    off_line = OBSTACLE_RADIUS_M + BODY_RADIUS_M + 0.45
    inside_window = _obstacle(1.0, off_line)
    assert SafetyMonitor().check(_robot(), (inside_window,), _segment(), DT_S) is EStopReason.NONE


def test_lateral_obstacle_exactly_at_the_clearance_is_not_skipped():
    segment = _segment()
    on_boundary = OBSTACLE_RADIUS_M + BODY_RADIUS_M
    assert segment.perpendicular_offset(1.0, on_boundary) == pytest.approx(on_boundary)
    request = SafetyMonitor().check(_robot(), (_obstacle(1.0, on_boundary),), segment, DT_S)
    assert request is EStopReason.SAFETY_DISTANCE

    just_outside = SafetyMonitor().check(_robot(), (_obstacle(1.0, on_boundary + 1e-6),), segment, DT_S)
    assert just_outside is EStopReason.NONE


def test_near_edge_exactly_at_the_lookahead_end_triggers():
    segment = _segment()
    window_end = _lookahead_m(V_MAX_MPS)
    center = window_end + OBSTACLE_RADIUS_M
    assert SafetyMonitor().check(_robot(), (_obstacle(center, 0.0),), segment, DT_S) is EStopReason.SAFETY_DISTANCE
    assert (
        SafetyMonitor().check(_robot(), (_obstacle(center + 1e-6, 0.0),), segment, DT_S) is EStopReason.NONE
    )


def test_obstacle_behind_the_robot_is_not_in_the_window():
    segment = _segment()
    request = SafetyMonitor().check(_robot(x=6.0), (_obstacle(5.0, 0.0),), segment, DT_S)
    assert request is EStopReason.NONE


def test_lookahead_window_is_truncated_at_the_segment_end():
    segment = _segment()
    robot = _robot(x=9.0)
    assert 9.0 + _lookahead_m(V_MAX_MPS) > EDGE_LENGTH_M
    # Reachable only if the window crossed into the next segment, which it must not.
    beyond_end = SafetyMonitor().check(robot, (_obstacle(EDGE_LENGTH_M + 0.25, 0.0),), segment, DT_S)
    assert beyond_end is EStopReason.NONE
    # A center past the node whose near edge is still inside this segment is in scope.
    straddling = SafetyMonitor().check(robot, (_obstacle(EDGE_LENGTH_M + 0.02, 0.0),), segment, DT_S)
    assert straddling is EStopReason.SAFETY_DISTANCE


def test_coverage_interval_exactly_touching_the_segment_end_triggers():
    segment = _segment()
    robot = _robot(x=9.0)
    touching = SafetyMonitor().check(robot, (_obstacle(EDGE_LENGTH_M + OBSTACLE_RADIUS_M, 0.0),), segment, DT_S)
    assert touching is EStopReason.SAFETY_DISTANCE
    outside = SafetyMonitor().check(
        robot, (_obstacle(EDGE_LENGTH_M + OBSTACLE_RADIUS_M + 1e-6, 0.0),), segment, DT_S
    )
    assert outside is EStopReason.NONE


def test_overlap_takes_precedence_and_reports_overlap():
    segment = _segment()
    touching = Obstacle("OBS", BODY_RADIUS_M + OBSTACLE_RADIUS_M, 0.0, OBSTACLE_RADIUS_M)
    assert SafetyMonitor().check(_robot(), (touching,), segment, DT_S) is EStopReason.SAFETY_DISTANCE
    assert math.hypot(touching.center_x, touching.center_y) == BODY_RADIUS_M + OBSTACLE_RADIUS_M

    inside = Obstacle("OBS", BODY_RADIUS_M + OBSTACLE_RADIUS_M - 1e-6, 0.0, OBSTACLE_RADIUS_M)
    assert SafetyMonitor().check(_robot(), (inside,), segment, DT_S) is EStopReason.OVERLAP


def test_body_circle_contact_is_overlap_even_when_lateral():
    segment = _segment()
    obstacle = Obstacle("OBS", 0.3, 0.35, OBSTACLE_RADIUS_M)
    assert math.hypot(obstacle.center_x, obstacle.center_y) < BODY_RADIUS_M + OBSTACLE_RADIUS_M
    assert SafetyMonitor().check(_robot(), (obstacle,), segment, DT_S) is EStopReason.OVERLAP


def test_a_stopped_robot_only_reacts_to_contact():
    segment = _segment()
    stopped = _robot(v_mps=0.0)
    assert SafetyMonitor().check(stopped, (_obstacle(0.6, 0.0),), segment, DT_S) is EStopReason.NONE
    assert SafetyMonitor().check(stopped, (_obstacle(0.5, 0.0),), segment, DT_S) is EStopReason.OVERLAP


def test_field_rejects_bad_radius_without_changing_the_set():
    field = ObstacleField()
    for bad_radius in (0.0, -1.0, 6.0):
        result = field.register(Obstacle("OBS", 1.0, 1.0, bad_radius))
        assert not result.accepted
        assert result.rejection is ObstacleRejection.INVALID_RADIUS
        assert field.active() == ()


def test_field_rejects_duplicate_id_without_changing_the_set():
    field = ObstacleField()
    assert field.register(Obstacle("OBS", 1.0, 1.0, 0.2)).accepted
    kept = field.active()
    result = field.register(Obstacle("OBS", 9.0, 9.0, 0.3))
    assert not result.accepted
    assert result.rejection is ObstacleRejection.DUPLICATE_ID
    assert field.active() == kept


def test_field_accepts_registration_inside_a_braking_distance():
    field = ObstacleField()
    stopping_distance = V_MAX_MPS * V_MAX_MPS / (2.0 * DECEL_MAX_MPS2)
    result = field.register(Obstacle("OBS", stopping_distance / 2.0, 0.0, OBSTACLE_RADIUS_M))
    assert result.accepted
    assert len(field.active()) == 1


def test_deregister_unknown_id_reports_not_found_and_keeps_the_set():
    field = ObstacleField((Obstacle("OBS", 1.0, 1.0, 0.2),))
    result = field.deregister("GHOST")
    assert not result.accepted
    assert result.rejection is ObstacleRejection.NOT_FOUND
    assert [item.obstacle_id for item in field.active()] == ["OBS"]

    assert field.deregister("OBS").accepted
    assert field.active() == ()


def test_active_obstacles_are_ordered_by_identifier():
    field = ObstacleField()
    for obstacle_id in ("O3", "O1", "O2"):
        assert field.register(Obstacle(obstacle_id, 1.0, 1.0, 0.2)).accepted
    assert [item.obstacle_id for item in field.active()] == ["O1", "O2", "O3"]


@pytest.mark.parametrize("dt", [DT_S, 0.05])
def test_a_robot_cruising_at_the_dt_ceiling_stops_short_of_a_straddling_obstacle(dt):
    """The design case: obstacle center past the node, near edge still inside this segment."""
    field = make_obstacle_field([obstacle_at(EDGE_LENGTH_M + 0.05, 0.0)])
    spec = make_spec(path=("N01", "N02", "N03"))
    robot = make_robot(load_map(MINIMAL_MAP_ID), spec=spec, dt=dt, obstacles=field)
    robot.receive(MotionCommand(CommandKind.ASSIGN_PATH, spec.robot_id, spec.planned_node_path))

    for _ in range(4000):
        robot.tick()
        if robot.status is RobotStatus.E_STOP and robot.v_mps == 0.0:
            break
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    assert robot.pose.x < EDGE_LENGTH_M, "the stop stays inside the current segment"
    assert robot.segment_index == 0
    gap = math.hypot(robot.pose.x - (EDGE_LENGTH_M + 0.05), robot.pose.y)
    assert gap >= BODY_RADIUS_M + OBSTACLE_RADIUS_M, "the two circles must not intersect"


def test_a_preset_obstacle_scenario_never_reports_overlap_at_the_dt_ceiling():
    field = make_obstacle_field([obstacle_at(5.0, 0.0)])
    spec = make_spec(path=("N01", "N02", "N03"))
    robot = make_robot(load_map(MINIMAL_MAP_ID), spec=spec, dt=0.05, obstacles=field)
    robot.receive(MotionCommand(CommandKind.ASSIGN_PATH, spec.robot_id, spec.planned_node_path))

    reasons = set()
    for _ in range(4000):
        robot.tick()
        if robot.estop_reason is not EStopReason.NONE:
            reasons.add(robot.estop_reason)
        if robot.status is RobotStatus.E_STOP and robot.v_mps == 0.0:
            break
    assert reasons == {EStopReason.SAFETY_DISTANCE}, "the fallback branch must not be reached"
    assert robot.pose.x < 5.0
    assert math.hypot(robot.pose.x - 5.0, robot.pose.y) >= BODY_RADIUS_M + OBSTACLE_RADIUS_M


def test_a_peer_circle_ahead_inside_the_window_triggers_like_an_obstacle():
    peer = _obstacle(1.0, 0.0, radius_m=BODY_RADIUS_M)
    assert SafetyMonitor().check(_robot(), (), _segment(), DT_S, peers=(peer,)) is EStopReason.SAFETY_DISTANCE


def test_a_lateral_peer_outside_the_clearance_is_skipped():
    peer = _obstacle(1.0, 2.0 * BODY_RADIUS_M + 0.01, radius_m=BODY_RADIUS_M)
    assert SafetyMonitor().check(_robot(), (), _segment(), DT_S, peers=(peer,)) is EStopReason.NONE


def test_a_peer_circle_overlap_is_reported_even_when_lateral():
    peer = _obstacle(0.3, BODY_RADIUS_M, radius_m=BODY_RADIUS_M)
    assert SafetyMonitor().check(_robot(), (), _segment(), DT_S, peers=(peer,)) is EStopReason.OVERLAP


def test_peers_and_registered_obstacles_share_one_judgement():
    peer = _obstacle(8.0, 0.0, radius_m=BODY_RADIUS_M)
    obstacle = _obstacle(1.0, 0.0)
    assert (
        SafetyMonitor().check(_robot(), (obstacle,), _segment(), DT_S, peers=(peer,))
        is EStopReason.SAFETY_DISTANCE
    )
