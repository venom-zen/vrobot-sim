"""Unit tests for the per-segment speed profile, node turning and arrival predicates."""

from __future__ import annotations

import math

import pytest
from conftest import (
    A_MAX_MPS2,
    ARRIVAL_TOLERANCE_M,
    ASSERT_TOL,
    BODY_RADIUS_M,
    DECEL_MAX_MPS2,
    DT_S,
    OMEGA_MAX_RADPS,
    TURN_ALIGN_TOLERANCE_RAD,
    V_MAX_MPS,
)

from vrobot_sim.controller import Controller
from vrobot_sim.kinematics import Pose, advance_pose, normalize_theta
from vrobot_sim.robot import ChassisConfig

SEGMENT_LENGTH_M = 10.0


def _controller(**overrides) -> Controller:
    return Controller(ChassisConfig(**overrides), DT_S)


def test_default_chassis_matches_the_parameters_declared_in_the_design():
    chassis = ChassisConfig()
    assert (
        chassis.v_max_mps,
        chassis.a_max_mps2,
        chassis.decel_max_mps2,
        chassis.omega_max_radps,
        chassis.body_radius_m,
        chassis.turn_align_tolerance_rad,
        chassis.arrival_tolerance_m,
    ) == (
        V_MAX_MPS,
        A_MAX_MPS2,
        DECEL_MAX_MPS2,
        OMEGA_MAX_RADPS,
        BODY_RADIUS_M,
        TURN_ALIGN_TOLERANCE_RAD,
        ARRIVAL_TOLERANCE_M,
    )


def test_profile_holds_at_the_braking_distance_and_bends_below_it():
    controller = _controller()
    braking_distance = V_MAX_MPS * V_MAX_MPS / (2.0 * A_MAX_MPS2)
    assert controller.linear_step(V_MAX_MPS, braking_distance) == pytest.approx(V_MAX_MPS, abs=ASSERT_TOL)
    assert controller.linear_step(V_MAX_MPS, braking_distance + 0.01) <= V_MAX_MPS + ASSERT_TOL

    decelerated = controller.linear_step(V_MAX_MPS, braking_distance - 0.01)
    assert decelerated < V_MAX_MPS
    assert V_MAX_MPS - decelerated <= A_MAX_MPS2 * DT_S + ASSERT_TOL


def test_cruise_is_capped_at_the_linear_speed_limit():
    controller = _controller()
    speed = 0.0
    for _ in range(200):
        speed = controller.linear_step(speed, SEGMENT_LENGTH_M)
        assert speed <= V_MAX_MPS + ASSERT_TOL
    assert speed == pytest.approx(V_MAX_MPS, abs=ASSERT_TOL)


def test_full_segment_profile_respects_acceleration_and_stops_at_the_segment_end():
    controller = _controller()
    speed = 0.0
    remaining = SEGMENT_LENGTH_M
    steps = 0
    peak = 0.0
    decelerating = False
    while not controller.segment_finished(remaining, speed):
        previous = speed
        speed = controller.linear_step(speed, remaining)
        remaining -= speed * DT_S
        steps += 1
        assert speed <= V_MAX_MPS + ASSERT_TOL
        # The one-step discretisation may carry the robot past the node by no more than
        # the arrival threshold, which the segment switch then resolves exactly.
        assert remaining >= -ARRIVAL_TOLERANCE_M
        if speed > previous + ASSERT_TOL:
            assert not decelerating, "the trapezoid must not speed up again once braking started"
            assert speed - previous <= A_MAX_MPS2 * DT_S + ASSERT_TOL
        elif speed < previous - ASSERT_TOL:
            decelerating = True
            assert previous - speed <= A_MAX_MPS2 * DT_S + ASSERT_TOL
        peak = max(peak, speed)
        assert steps < 2000

    assert speed == 0.0
    assert -ARRIVAL_TOLERANCE_M <= remaining <= ARRIVAL_TOLERANCE_M
    assert peak == pytest.approx(V_MAX_MPS, rel=1e-6)


def test_short_segment_never_exceeds_the_limits_and_still_stops():
    controller = _controller()
    for length in (0.25, 1.0, 3.0):
        speed = 0.0
        remaining = length
        steps = 0
        while not controller.segment_finished(remaining, speed):
            previous = speed
            speed = controller.linear_step(speed, remaining)
            remaining -= speed * DT_S
            assert previous - speed <= A_MAX_MPS2 * DT_S + ASSERT_TOL
            assert speed - previous <= A_MAX_MPS2 * DT_S + ASSERT_TOL
            assert remaining >= -ARRIVAL_TOLERANCE_M
            steps += 1
            assert steps < 2000
        assert remaining <= ARRIVAL_TOLERANCE_M


def test_estop_step_uses_the_emergency_deceleration_limit():
    controller = _controller()
    speed = V_MAX_MPS
    drops = []
    while speed > 0.0:
        previous = speed
        speed = controller.estop_step(speed)
        drops.append(previous - speed)
        assert speed >= 0.0
    assert max(drops) == pytest.approx(DECEL_MAX_MPS2 * DT_S, abs=ASSERT_TOL)
    assert all(drop <= DECEL_MAX_MPS2 * DT_S + ASSERT_TOL for drop in drops)


def test_turn_completes_at_exactly_the_alignment_tolerance():
    controller = _controller()
    target = controller.turn_step(TURN_ALIGN_TOLERANCE_RAD)
    assert target.aligned
    assert target.omega_radps == pytest.approx(TURN_ALIGN_TOLERANCE_RAD / DT_S, abs=ASSERT_TOL)
    assert target.omega_radps <= OMEGA_MAX_RADPS + TURN_ALIGN_TOLERANCE_RAD

    beyond = controller.turn_step(TURN_ALIGN_TOLERANCE_RAD + 1e-12)
    assert not beyond.aligned


def test_turn_direction_follows_the_sign_of_the_remaining_angle():
    controller = _controller()
    assert controller.turn_step(-1.0).omega_radps == pytest.approx(-OMEGA_MAX_RADPS, abs=ASSERT_TOL)
    assert controller.turn_step(1.0).omega_radps == pytest.approx(OMEGA_MAX_RADPS, abs=ASSERT_TOL)


def test_full_turn_lands_on_the_exact_segment_heading_without_overshoot():
    controller = _controller()
    heading = math.pi / 2.0
    pose = Pose(10.0, 0.0, 0.0)
    remaining = normalize_theta(heading - pose.theta)
    steps = 0
    while True:
        target = controller.turn_step(remaining)
        pose = advance_pose(pose, 0.0, target.omega_radps, DT_S, heading)
        assert abs(target.omega_radps) <= OMEGA_MAX_RADPS + TURN_ALIGN_TOLERANCE_RAD
        assert abs(pose.theta - heading) <= abs(remaining) + ASSERT_TOL
        remaining = normalize_theta(heading - pose.theta)
        steps += 1
        if target.aligned:
            pose = Pose(pose.x, pose.y, normalize_theta(heading))
            break
        assert steps < 500

    assert pose.theta == heading
    assert (pose.x, pose.y) == (10.0, 0.0)
    assert abs(remaining) <= TURN_ALIGN_TOLERANCE_RAD
    assert steps == pytest.approx(math.ceil((math.pi / 2.0) / (OMEGA_MAX_RADPS * DT_S)), abs=2)
