"""E-stop cases through the kernel: approach, straddling, late contact and recovery."""

from __future__ import annotations

import math

import pytest
from conftest import (
    ASSERT_TOL,
    BODY_RADIUS_M,
    DECEL_MAX_MPS2,
    DT_S,
    V_MAX_MPS,
    assign_path,
    make_spec,
    obstacle_at,
    resume,
)

from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.obstacle_field import Obstacle
from vrobot_sim.robot import CommandRejection, EStopReason, RobotStatus
from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation

PATH = ("N01", "N02", "N03")
RADIUS_M = 0.2
NODE_N02_X_M = 10.0
NODE_N03_Y_M = 5.0


class _DemandCommandSource:
    """Delivers the planned path once, then whatever command the test asks for next step."""

    def __init__(self, spec):
        self._spec = spec
        self._assign_pending = True
        self._pending = []
        self.results = []

    def request_resume(self) -> None:
        self._pending.append(resume(self._spec.robot_id))

    def request_assign(self, path: tuple[str, ...]) -> None:
        self._pending.append(assign_path(self._spec.robot_id, path))

    def dispatch(self, tick_index: int, robots) -> None:
        targets = {robot.robot_id: robot for robot in robots}
        if self._assign_pending:
            self._assign_pending = False
            self.request_assign(self._spec.planned_node_path)
        for command in self._pending:
            self.results.append(targets[command.robot_id].receive(command))
        self._pending.clear()


def _scenario(obstacles: tuple[Obstacle, ...] = ()) -> Scenario:
    return Scenario(map_id=MINIMAL_MAP_ID, dt_s=DT_S, robots=(make_spec(path=PATH),), obstacles=obstacles)


def _drive(sim: Simulation, ticks: int, stop_when=None) -> list:
    """Collect one record per tick for the scenario's single robot."""
    records = []
    for _ in range(ticks):
        robot = sim.step().robots[0]
        records.append(robot)
        if stop_when is not None and stop_when(robot):
            break
    return records


def _create_with_source(obstacles: tuple[Obstacle, ...] = ()):
    spec = make_spec(path=PATH)
    source = _DemandCommandSource(spec)
    scenario = Scenario(map_id=MINIMAL_MAP_ID, dt_s=DT_S, robots=(spec,), obstacles=obstacles)
    return Simulation.create(scenario, command_source=source), source


def _stopped(robot) -> bool:
    return robot.status is RobotStatus.E_STOP and robot.v_mps == 0.0


def test_a_preset_obstacle_makes_the_robot_stop_before_touching_it():
    sim = Simulation.create(_scenario((obstacle_at(5.0, 0.0, RADIUS_M),)))
    records = _drive(sim, 900, stop_when=_stopped)
    trigger = next(item for item in records if item.estop_reason is not EStopReason.NONE)
    assert trigger.estop_reason is EStopReason.SAFETY_DISTANCE

    final = records[-1]
    assert final.status is RobotStatus.E_STOP and final.v_mps == 0.0
    assert math.hypot(final.x_m - 5.0, final.y_m) >= BODY_RADIUS_M + RADIUS_M
    assert final.x_m < NODE_N02_X_M
    assert all(item.omega_radps == 0.0 for item in records), "the linear sub-phase is kept"


def test_the_approach_case_reports_exactly_one_reason_value():
    sim = Simulation.create(_scenario((obstacle_at(5.0, 0.0, RADIUS_M),)))
    reasons = {item.estop_reason for item in _drive(sim, 900) if item.estop_reason is not EStopReason.NONE}
    assert reasons == {EStopReason.SAFETY_DISTANCE}


def test_every_braking_step_obeys_the_emergency_limit():
    sim = Simulation.create(_scenario((obstacle_at(5.0, 0.0, RADIUS_M),)))
    previous = 0.0
    braking = False
    for _ in range(900):
        robot = sim.step().robots[0]
        braking = braking or robot.status is RobotStatus.E_STOP
        if braking:
            assert previous - robot.v_mps <= DECEL_MAX_MPS2 * DT_S + ASSERT_TOL
        previous = robot.v_mps
    assert previous == 0.0


def test_a_straddling_obstacle_is_seen_on_the_current_segment():
    sim = Simulation.create(_scenario((obstacle_at(NODE_N02_X_M + 0.05, 0.0, RADIUS_M),)))
    final = _drive(sim, 900, stop_when=_stopped)[-1]
    assert final.estop_reason is EStopReason.SAFETY_DISTANCE
    assert final.x_m < NODE_N02_X_M, "the stop happens before the node"
    assert math.hypot(final.x_m - (NODE_N02_X_M + 0.05), final.y_m) >= BODY_RADIUS_M + RADIUS_M


@pytest.mark.parametrize(
    ("center_m", "expected_reason"),
    [(4.0, EStopReason.SAFETY_DISTANCE), (0.3, EStopReason.OVERLAP)],
)
def test_the_reason_follows_whether_the_body_circle_already_intersects(center_m, expected_reason):
    sim = Simulation.create(_scenario((obstacle_at(center_m, 0.0, RADIUS_M),)))
    stopped_at_request = _drive(sim, 400, stop_when=lambda item: item.status is RobotStatus.E_STOP)[-1]
    assert stopped_at_request.estop_reason is expected_reason
    if expected_reason is EStopReason.SAFETY_DISTANCE:
        _drive(sim, 200, stop_when=_stopped)

    settled = sim.step().robots[0]
    assert settled.status is RobotStatus.E_STOP
    assert settled.v_mps == 0.0


def test_an_obstacle_registered_late_zeroes_the_speed_on_the_next_tick():
    sim = Simulation.create(_scenario())
    _drive(sim, 200)
    moving = sim.step().robots[0]
    assert moving.status is RobotStatus.MOVING
    assert moving.v_mps == pytest.approx(V_MAX_MPS, abs=ASSERT_TOL)

    assert sim.obstacles.register(obstacle_at(moving.x_m + BODY_RADIUS_M + 0.1, 0.0, RADIUS_M)).accepted
    robot = sim.step().robots[0]
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.OVERLAP
    assert robot.v_mps == 0.0 and robot.omega_radps == 0.0


def test_a_contact_while_braking_rewrites_the_recorded_reason():
    sim = Simulation.create(_scenario((obstacle_at(6.0, 0.0, RADIUS_M),)))
    braking = _drive(sim, 900, stop_when=lambda item: item.status is RobotStatus.E_STOP and item.v_mps > 0.0)[-1]
    assert braking.estop_reason is EStopReason.SAFETY_DISTANCE

    late = obstacle_at(braking.x_m + BODY_RADIUS_M + 0.1, 0.0, RADIUS_M, obstacle_id="LATE")
    assert sim.obstacles.register(late).accepted
    robot = sim.step().robots[0]
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.OVERLAP
    assert robot.v_mps == 0.0


def test_resume_into_a_blocked_path_keeps_the_e_stop_and_the_pose():
    sim, source = _create_with_source((obstacle_at(5.0, 0.0, RADIUS_M),))
    blocked = _drive(sim, 900, stop_when=_stopped)[-1]
    source.request_resume()
    robot = sim.step().robots[0]

    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    assert (robot.x_m, robot.y_m) == (blocked.x_m, blocked.y_m)
    assert robot.v_mps == 0.0


def test_after_the_obstacle_is_removed_the_robot_finishes_the_remaining_path():
    sim, source = _create_with_source((obstacle_at(5.0, 0.0, RADIUS_M),))
    stopped = _drive(sim, 900, stop_when=_stopped)[-1]
    assert stopped.x_m > 3.0, "the robot stopped partway, not at the start"

    assert sim.obstacles.deregister("OBS").accepted
    source.request_resume()
    final = _drive(sim, 1500, stop_when=lambda item: item.status is RobotStatus.ARRIVED)[-1]
    assert final.status is RobotStatus.ARRIVED
    assert (final.x_m, final.y_m) == (NODE_N02_X_M, NODE_N03_Y_M)
    assert final.x_m >= stopped.x_m


def test_a_stopped_robot_ignores_an_empty_lookahead_without_a_resume():
    sim = Simulation.create(_scenario((obstacle_at(5.0, 0.0, RADIUS_M),)))
    _drive(sim, 900, stop_when=_stopped)
    assert sim.obstacles.deregister("OBS").accepted
    for _ in range(60):
        robot = sim.step().robots[0]
        assert robot.status is RobotStatus.E_STOP
        assert robot.v_mps == 0.0


def test_assign_path_during_an_e_stop_is_refused_by_the_intake_boundary():
    sim, source = _create_with_source((obstacle_at(5.0, 0.0, RADIUS_M),))
    stopped = _drive(sim, 900, stop_when=_stopped)[-1]
    source.request_assign(("N01", "N02"))

    robot = sim.step().robots[0]
    assert robot.status is RobotStatus.E_STOP
    assert (robot.x_m, robot.y_m) == (stopped.x_m, stopped.y_m)
    assert robot.v_mps == 0.0
    assert source.results[-1].rejection is CommandRejection.INVALID_STATE


def test_resume_while_moving_is_refused_and_motion_continues():
    sim, source = _create_with_source()
    _drive(sim, 100)
    source.request_resume()
    robot = sim.step().robots[0]

    assert robot.status is RobotStatus.MOVING
    assert robot.v_mps > 0.0
    assert source.results[-1].rejection is CommandRejection.INVALID_STATE
