"""State machine and command intake boundary tests for the robot runtime object."""

from __future__ import annotations

import math

import pytest
from conftest import (
    ASSERT_TOL,
    BODY_RADIUS_M,
    DECEL_MAX_MPS2,
    DT_S,
    V_MAX_MPS,
    ScriptedCommandSource,
    make_obstacle_field,
    make_robot,
    make_spec,
    obstacle_at,
    read_state,
)

from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.obstacle_field import ObstacleField
from vrobot_sim.robot import (
    CommandKind,
    CommandRejection,
    CommandSource,
    MotionCommand,
    PassthroughCommandSource,
    Robot,
    RobotStatus,
    EStopReason,
)

RIGHT_ANGLE_RAD = math.pi / 2.0
MINIMAL = MINIMAL_MAP_ID
OBSTACLE_ON_E01_M = 5.0


def _assign(robot_id: str, path: tuple[str, ...]) -> MotionCommand:
    return MotionCommand(kind=CommandKind.ASSIGN_PATH, robot_id=robot_id, node_path=path)


def _resume(robot_id: str) -> MotionCommand:
    return MotionCommand(kind=CommandKind.RESUME, robot_id=robot_id)


def _run(robot: Robot, max_ticks: int, stop_when=None) -> list:
    states = []
    for _ in range(max_ticks):
        robot.tick()
        states.append(read_state(robot))
        if stop_when is not None and stop_when(robot):
            break
    return states


def _minimal_robot(path=("N01", "N02", "N03"), obstacles=None, theta=0.0):
    field = obstacles if obstacles is not None else ObstacleField()
    spec = make_spec(path=path, start_theta_rad=theta)
    return make_robot(load_map(MINIMAL), spec=spec, obstacles=field), field


def _cruise_until(robot: Robot, predicate, max_ticks: int = 2000):
    for _ in range(max_ticks):
        robot.tick()
        if predicate(robot):
            return True
    return False


def test_accepted_path_enters_moving_and_arrives_at_the_final_node():
    robot, _ = _minimal_robot()
    result = robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert result.accepted
    assert robot.status is RobotStatus.MOVING
    assert robot.path_edge_ids == ("E01", "E02")
    assert robot.estop_reason is EStopReason.NONE

    _run(robot, 4000, stop_when=lambda item: item.status is RobotStatus.ARRIVED)
    assert robot.status is RobotStatus.ARRIVED
    assert (robot.pose.x, robot.pose.y) == (10.0, 5.0)
    assert robot.pose.theta == pytest.approx(RIGHT_ANGLE_RAD, abs=ASSERT_TOL)
    assert robot.v_mps == 0.0 and robot.omega_radps == 0.0
    assert robot.segment_index == 1

    before = read_state(robot)
    _run(robot, 20)
    assert read_state(robot) == before, "an arrived robot no longer turns or moves"


def test_segment_end_zeroes_the_speed_then_turns_in_place_at_the_node():
    robot, _ = _minimal_robot()
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    turning_at_node = []
    for _ in range(2000):
        robot.tick()
        if robot.pose.x == 10.0 and robot.pose.y == 0.0 and robot.status is RobotStatus.MOVING:
            turning_at_node.append((robot.v_mps, robot.turn_remaining_rad, robot.segment_remaining_m))
            if len(turning_at_node) > 3:
                break
    assert turning_at_node
    for speed, turn_remaining, segment_remaining in turning_at_node:
        assert speed == 0.0, "the segment end is a full stop"
        assert turn_remaining > 0.0, "the robot is in the turning sub-phase"
        assert segment_remaining == 0.0


def test_initial_heading_mismatch_is_corrected_before_straight_line_motion():
    robot, _ = _minimal_robot(path=("N01", "N02"), theta=RIGHT_ANGLE_RAD)
    robot.receive(_assign("R1", ("N01", "N02")))
    assert robot.turn_remaining_rad == pytest.approx(-RIGHT_ANGLE_RAD, abs=ASSERT_TOL)

    states = []
    for _ in range(200):
        robot.tick()
        states.append(read_state(robot))
        if robot.segment_remaining_m > 0.0:
            break
    assert all(state[0] == 0.0 and state[1] == 0.0 for state in states), "no travel while turning"
    assert robot.pose.theta == pytest.approx(0.0, abs=ASSERT_TOL)
    assert robot.status is RobotStatus.MOVING


def test_path_with_a_missing_edge_is_rejected_and_leaves_the_robot_untouched():
    robot, _ = _minimal_robot()
    result = robot.receive(_assign("R1", ("N01", "N03")))
    assert not result.accepted
    assert result.rejection is CommandRejection.PATH_UNAVAILABLE
    assert any("('N01', 'N03')" in item for item in result.violations)
    assert robot.status is RobotStatus.IDLE
    assert (robot.pose.x, robot.pose.y) == (0.0, 0.0)
    assert robot.v_mps == 0.0


def test_path_with_an_unknown_node_lists_that_identifier():
    robot, _ = _minimal_robot()
    result = robot.receive(_assign("R1", ("N01", "GHOST")))
    assert result.rejection is CommandRejection.PATH_UNAVAILABLE
    assert any("GHOST" in item for item in result.violations)


def test_path_starting_on_another_node_names_both_identifiers():
    robot, _ = _minimal_robot()
    result = robot.receive(_assign("R1", ("N02", "N03")))
    assert result.rejection is CommandRejection.PATH_UNAVAILABLE
    assert len(result.violations) == 1
    assert "N02" in result.violations[0]
    assert "N01" in result.violations[0]
    assert robot.status is RobotStatus.IDLE


def test_travelling_a_one_way_edge_backwards_uses_the_same_structured_rejection():
    spec = make_spec(robot_id="R9", path=("N03", "N02"), start_node_id="N03", start_theta_rad=math.pi)
    robot = make_robot(load_map(DEMO_MAP_ID), spec=spec)
    result = robot.receive(_assign("R9", ("N03", "N02")))
    assert not result.accepted
    assert result.rejection is CommandRejection.PATH_UNAVAILABLE
    assert any("E02" in item and "one-way" in item for item in result.violations)
    assert robot.status is RobotStatus.IDLE


def test_every_problem_in_a_path_is_reported_in_one_answer():
    spec = make_spec(robot_id="R9", path=("N01", "N02"), start_node_id="N01")
    robot = make_robot(load_map(DEMO_MAP_ID), spec=spec)
    result = robot.receive(_assign("R9", ("N04", "N05", "N01")))
    assert result.rejection is CommandRejection.PATH_UNAVAILABLE
    assert len(result.violations) == 2
    assert any("N04" in item and "N01" in item for item in result.violations)
    assert any("('N05', 'N01')" in item for item in result.violations)


@pytest.mark.parametrize(
    ("status_setup", "expected_status"),
    [("idle", RobotStatus.IDLE), ("moving", RobotStatus.MOVING), ("arrived", RobotStatus.ARRIVED)],
)
def test_resume_outside_e_stop_is_an_invalid_state_rejection(status_setup, expected_status):
    robot, _ = _minimal_robot()
    if status_setup != "idle":
        robot.receive(_assign("R1", ("N01", "N02")))
        _run(robot, 20)
    if status_setup == "arrived":
        assert _cruise_until(robot, lambda item: item.status is RobotStatus.ARRIVED)
    before = read_state(robot)
    assert robot.status is expected_status

    result = robot.receive(_resume("R1"))
    assert not result.accepted
    assert result.rejection is CommandRejection.INVALID_STATE
    assert read_state(robot) == before


def test_assign_path_while_moving_is_rejected_by_the_state_gate():
    robot, _ = _minimal_robot()
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    _run(robot, 20)
    before = read_state(robot)
    result = robot.receive(_assign("R1", ("N01", "N02")))
    assert result.rejection is CommandRejection.INVALID_STATE
    assert read_state(robot) == before


def test_stopping_at_the_safety_distance_then_resuming_completes_the_remaining_path():
    field = make_obstacle_field([obstacle_at(OBSTACLE_ON_E01_M, 0.0)])
    robot, _ = _minimal_robot(path=("N01", "N02", "N03"), obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))

    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    _run(robot, 200)
    assert robot.v_mps == 0.0
    assert robot.segment_index == 0, "the e-stop must not switch segments"
    assert robot.turn_remaining_rad == 0.0, "the linear sub-phase is kept"
    assert robot.pose.x < 10.0, "the stop happens before the segment end"
    distance = math.hypot(robot.pose.x - OBSTACLE_ON_E01_M, robot.pose.y)
    assert distance >= BODY_RADIUS_M + 0.2, "a safety-distance stop must not touch the obstacle"

    still_blocked = robot.receive(_resume("R1"))
    assert still_blocked.accepted
    assert robot.status is RobotStatus.E_STOP, "resume into a blocked path stays an e-stop"

    assert field.deregister("OBS").accepted
    robot.receive(_resume("R1"))
    assert robot.status is RobotStatus.MOVING
    assert robot.estop_reason is EStopReason.NONE
    assert robot.pose.x > 4.0, "the robot continues instead of starting over"

    _run(robot, 4000, stop_when=lambda item: item.status is RobotStatus.ARRIVED)
    assert robot.status is RobotStatus.ARRIVED
    assert (robot.pose.x, robot.pose.y) == (10.0, 5.0)


def test_resume_with_the_hazard_still_present_leaves_the_pose_untouched():
    field = make_obstacle_field([obstacle_at(OBSTACLE_ON_E01_M, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)
    _run(robot, 100)
    before = read_state(robot)

    result = robot.receive(_resume("R1"))
    assert result.accepted
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    assert read_state(robot) == before


def test_assign_path_during_an_e_stop_changes_nothing():
    field = make_obstacle_field([obstacle_at(OBSTACLE_ON_E01_M, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)
    before = read_state(robot)
    before_path = robot.path_edge_ids

    result = robot.receive(_assign("R1", ("N01", "N02")))
    assert not result.accepted
    assert result.rejection is CommandRejection.INVALID_STATE
    assert robot.path_edge_ids == before_path
    assert read_state(robot) == before
    assert robot.status is RobotStatus.E_STOP


def test_every_e_stop_deceleration_step_respects_the_emergency_limit():
    field = make_obstacle_field([obstacle_at(OBSTACLE_ON_E01_M, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)

    previous = robot.v_mps
    for _ in range(200):
        robot.tick()
        assert previous - robot.v_mps <= DECEL_MAX_MPS2 * DT_S + ASSERT_TOL
        assert robot.v_mps >= 0.0
        previous = robot.v_mps
    assert robot.v_mps == 0.0


def test_an_obstacle_registered_late_zeroes_the_speed_on_contact():
    robot, field = _minimal_robot()
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.v_mps == V_MAX_MPS)
    assert robot.status is RobotStatus.MOVING
    assert robot.estop_reason is EStopReason.NONE
    assert field.register(obstacle_at(robot.pose.x + BODY_RADIUS_M + 0.1, 0.0)).accepted
    assert robot.v_mps > 0.0

    robot.tick()
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.OVERLAP
    assert robot.v_mps == 0.0 and robot.omega_radps == 0.0


def test_a_robot_starting_inside_an_obstacle_stops_on_its_first_tick():
    field = make_obstacle_field([obstacle_at(0.3, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert robot.status is RobotStatus.MOVING

    robot.tick()
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.OVERLAP
    assert robot.v_mps == 0.0


def test_contact_while_braking_rewrites_the_reason_to_overlap():
    field = make_obstacle_field([obstacle_at(6.0, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    assert robot.v_mps > 0.0

    assert field.register(obstacle_at(robot.pose.x + BODY_RADIUS_M + 0.1, 0.0, obstacle_id="LATE")).accepted
    robot.tick()
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.OVERLAP
    assert robot.v_mps == 0.0


@pytest.mark.parametrize("map_id", [MINIMAL_MAP_ID, DEMO_MAP_ID])
def test_only_the_four_produced_states_ever_appear(map_id):
    map_obj = load_map(map_id)
    path = ("N01", "N02", "N03") if map_id == MINIMAL_MAP_ID else ("N01", "N02", "N04", "N05")
    spec = make_spec(path=path)
    robot = make_robot(map_obj, spec=spec)
    robot.receive(_assign("R1", path))
    states = _run(robot, 3000, stop_when=lambda item: item.status is RobotStatus.ARRIVED)
    observed = {state[5] for state in states} | {RobotStatus.IDLE}
    assert observed <= {
        RobotStatus.IDLE,
        RobotStatus.MOVING,
        RobotStatus.E_STOP,
        RobotStatus.ARRIVED,
    }
    assert robot.status is RobotStatus.ARRIVED


def test_swapping_the_command_source_keeps_per_tick_output_identical():
    """The body is untouched by a source swap: same Robot class, tick-for-tick identical output.

    "robot 与 kinematics 代码未修改" is a process property; the falsifiable part proven here is
    that a different producer drives the same class to byte-identical per-tick state.
    """
    assert isinstance(PassthroughCommandSource([]), CommandSource)
    path = ("N01", "N02", "N03")
    spec = make_spec(path=path)

    builtin = make_robot(load_map(MINIMAL), spec=spec)
    builtin_source = PassthroughCommandSource([spec])

    stand_in = make_robot(load_map(MINIMAL), spec=spec)
    stand_in_source = ScriptedCommandSource([(0, _assign("R1", path))])

    runs = {}
    for name, source, robot in (("builtin", builtin_source, builtin), ("stand_in", stand_in_source, stand_in)):
        states = []
        for tick in range(1200):
            source.dispatch(tick, [robot])
            robot.tick()
            states.append(read_state(robot))
            if robot.status is RobotStatus.ARRIVED:
                break
        runs[name] = states

    assert len(runs["builtin"]) > 100
    assert runs["builtin"] == runs["stand_in"]
    assert type(builtin) is type(stand_in) is Robot


def test_command_addressed_to_another_robot_is_structurally_rejected():
    robot, _ = _minimal_robot(path=("N01", "N02", "N03"))
    before = read_state(robot)

    result = robot.receive(_assign("OTHER", ("N01", "N02", "N03")))
    assert not result.accepted
    assert result.rejection is CommandRejection.TARGET_MISMATCH
    assert "OTHER" in result.violations[0] and "R1" in result.violations[0]
    assert read_state(robot) == before
    assert robot.path_node_ids == ()


def test_resume_carrying_a_node_path_is_rejected_without_changing_state():
    field = make_obstacle_field([obstacle_at(OBSTACLE_ON_E01_M, 0.0)])
    robot, _ = _minimal_robot(obstacles=field)
    robot.receive(_assign("R1", ("N01", "N02", "N03")))
    assert _cruise_until(robot, lambda item: item.status is RobotStatus.E_STOP)
    before = read_state(robot)

    result = robot.receive(
        MotionCommand(kind=CommandKind.RESUME, robot_id="R1", node_path=("N01", "N02"))
    )
    assert not result.accepted
    assert result.rejection is CommandRejection.MALFORMED_PAYLOAD
    assert "N01" in result.violations[0]
    assert read_state(robot) == before

    assert field.deregister("OBS").accepted
    assert robot.receive(_resume("R1")).accepted
    assert robot.status is RobotStatus.MOVING
