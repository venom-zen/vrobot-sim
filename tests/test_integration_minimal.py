"""Full task on the minimal map: per-tick constraint limits and analytic trajectory endpoints."""

from __future__ import annotations

import math

import pytest
from conftest import (
    A_MAX_MPS2,
    ARRIVAL_TOLERANCE_M,
    ASSERT_TOL,
    DT_S,
    OMEGA_MAX_RADPS,
    TURN_ALIGN_TOLERANCE_RAD,
    V_MAX_MPS,
    make_spec,
)

from vrobot_sim.maps import load_map
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.robot import RobotStatus
from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation

PATH = ("N01", "N02", "N03")
FIRST_SEGMENT_M = 10.0
NODE_N03_Y_M = 5.0
TURN_TICKS_ANALYTIC = math.ceil((math.pi / 2.0 - TURN_ALIGN_TOLERANCE_RAD) / (OMEGA_MAX_RADPS * DT_S)) + 1


def _drive(ticks: int = 2000):
    sim = Simulation.create(Scenario(map_id=MINIMAL_MAP_ID, dt_s=DT_S, robots=(make_spec(path=PATH),)))
    snapshots = [sim.step() for _ in range(ticks)]
    return sim, snapshots


def _series(snapshots):
    return [(item.robots[0].x_m, item.robots[0].y_m, item.robots[0].v_mps, item.robots[0].omega_radps)
            for item in snapshots]


def test_the_task_completes_on_the_analytic_endpoint_of_the_last_segment():
    _, snapshots = _drive(2000)
    final = snapshots[-1].robots[0]
    assert final.status is RobotStatus.ARRIVED
    assert (final.x_m, final.y_m) == (FIRST_SEGMENT_M, NODE_N03_Y_M)
    assert final.theta_rad == pytest.approx(math.pi / 2.0, abs=ASSERT_TOL)
    assert final.v_mps == 0.0 and final.omega_radps == 0.0


def test_line_speed_and_acceleration_stay_inside_their_limits_every_tick():
    _, snapshots = _drive(900)
    series = _series(snapshots)
    previous_speed = 0.0
    for _, _, speed, _ in series:
        assert speed <= V_MAX_MPS + ASSERT_TOL
        assert speed - previous_speed <= A_MAX_MPS2 * DT_S + ASSERT_TOL
        # No obstacle in this scenario, so every drop is a planned segment-end deceleration.
        assert previous_speed - speed <= A_MAX_MPS2 * DT_S + ASSERT_TOL
        previous_speed = speed
    assert max(item[2] for item in series) == pytest.approx(V_MAX_MPS, abs=ASSERT_TOL)


def test_cruise_begins_after_the_analytic_acceleration_distance():
    _, snapshots = _drive(300)
    braking_distance = V_MAX_MPS * V_MAX_MPS / (2.0 * A_MAX_MPS2)
    first_cruise = next(index for index, item in enumerate(_series(snapshots)) if item[2] == V_MAX_MPS)
    assert first_cruise == math.ceil(V_MAX_MPS / (A_MAX_MPS2 * DT_S)) - 1
    travelled = _series(snapshots)[first_cruise][0]
    assert braking_distance <= travelled <= braking_distance + 2 * V_MAX_MPS * DT_S


def test_the_turn_happens_in_place_at_the_node_at_the_angular_limit():
    _, snapshots = _drive(900)
    turning = [item for item in _series(snapshots) if abs(item[3]) > 0.0]
    assert len(turning) == TURN_TICKS_ANALYTIC
    assert max(abs(item[3]) for item in turning) == pytest.approx(OMEGA_MAX_RADPS, abs=ASSERT_TOL)
    for x, y, speed, _ in turning:
        assert (x, y) == (FIRST_SEGMENT_M, 0.0), "an in-place turn does not translate"
        assert speed == 0.0


def test_theta_stays_normalised_and_the_centroid_stays_on_the_centerline():
    map_obj = load_map(MINIMAL_MAP_ID)
    first = map_obj.segment_geometry("N01", "N02")
    second = map_obj.segment_geometry("N02", "N03")
    _, snapshots = _drive(900)
    switched = False
    for snapshot in snapshots:
        robot = snapshot.robots[0]
        assert -math.pi <= robot.theta_rad < math.pi
        segment = first if not switched else second
        if robot.x_m == FIRST_SEGMENT_M and robot.y_m > 0.0:
            switched = True
            segment = second
        # Float noise from sin/cos of the heading is not a cross-track offset.
        assert abs(segment.perpendicular_offset(robot.x_m, robot.y_m)) < 1e-12


def test_the_route_lands_exactly_on_the_intermediate_node_and_the_final_node():
    _, snapshots = _drive(900)
    series = _series(snapshots)
    at_node = [index for index, (x, y, _, _) in enumerate(series) if (x, y) == (FIRST_SEGMENT_M, 0.0)]
    assert at_node
    assert series[-1][:2] == (FIRST_SEGMENT_M, NODE_N03_Y_M)
    assert all(item[0] >= FIRST_SEGMENT_M - ASSERT_TOL for item in series[at_node[-1]:])


def test_the_centroid_never_passes_the_segment_end_by_more_than_the_threshold():
    _, snapshots = _drive(900)
    on_first_segment = [x for x, y, _, _ in _series(snapshots) if y == 0.0]
    assert on_first_segment
    assert max(on_first_segment) <= FIRST_SEGMENT_M + ARRIVAL_TOLERANCE_M
