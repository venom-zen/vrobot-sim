"""Unit tests for differential-drive pose integration and theta normalization."""

from __future__ import annotations

import math

import pytest
from conftest import ASSERT_TOL, DT_S, V_MAX_MPS

from vrobot_sim.kinematics import Pose, advance_pose, normalize_theta
from vrobot_sim.maps import load_map
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID

RIGHT_ANGLE_RAD = math.pi / 2.0


def test_linear_sub_stage_advances_along_the_segment_direction():
    pose = advance_pose(Pose(0.0, 0.0, 0.0), V_MAX_MPS, 0.0, DT_S, 0.0)
    assert pose.x == pytest.approx(V_MAX_MPS * DT_S, abs=ASSERT_TOL)
    assert pose.y == pytest.approx(0.0, abs=ASSERT_TOL)
    assert pose.theta == 0.0

    pose = advance_pose(Pose(10.0, 0.0, RIGHT_ANGLE_RAD), V_MAX_MPS, 0.0, DT_S, RIGHT_ANGLE_RAD)
    assert pose.x == pytest.approx(10.0, abs=ASSERT_TOL)
    assert pose.y == pytest.approx(V_MAX_MPS * DT_S, abs=ASSERT_TOL)
    assert pose.theta == pytest.approx(RIGHT_ANGLE_RAD, abs=ASSERT_TOL)


def test_linear_sub_stage_keeps_theta_at_the_segment_heading():
    pose = advance_pose(Pose(0.0, 0.0, -RIGHT_ANGLE_RAD), 1.0, 0.0, DT_S, math.pi)
    assert pose.theta == normalize_theta(math.pi)
    assert pose.x == pytest.approx(-DT_S, abs=ASSERT_TOL)
    assert pose.y == pytest.approx(0.0, abs=1e-15)


def test_turning_sub_stage_rotates_without_translation():
    pose = advance_pose(Pose(10.0, 0.0, 0.0), 0.0, 1.2, DT_S, RIGHT_ANGLE_RAD)
    assert pose.x == 10.0
    assert pose.y == 0.0
    assert pose.theta == pytest.approx(1.2 * DT_S, abs=ASSERT_TOL)


@pytest.mark.parametrize(
    ("raw_theta", "expected"),
    [
        (0.0, 0.0),
        (-math.pi, -math.pi),
        (math.pi, -math.pi),
        (3 * math.pi, -math.pi),
        (-3 * math.pi, -math.pi),
        (-0.001, -0.001),
        (math.pi - 1e-12, math.pi - 1e-12),
    ],
)
def test_normalize_theta_boundaries(raw_theta, expected):
    assert normalize_theta(raw_theta) == pytest.approx(expected, abs=ASSERT_TOL)
    assert -math.pi <= normalize_theta(raw_theta) < math.pi


def test_repeated_turns_stay_inside_the_half_open_interval():
    pose = Pose(0.0, 0.0, -math.pi)
    for _ in range(500):
        pose = advance_pose(pose, 0.0, 1.2, DT_S, 0.0)
        assert -math.pi <= pose.theta < math.pi
    assert pose.theta == pytest.approx(normalize_theta(500 * 1.2 * DT_S - math.pi), abs=1e-9)


def test_linear_sub_stage_never_develops_a_cross_track_offset():
    segment = load_map(MINIMAL_MAP_ID).segment_geometry("N02", "N03")
    pose = Pose(segment.start_x, segment.start_y, segment.heading_rad)
    for _ in range(60):
        pose = advance_pose(pose, V_MAX_MPS, 0.0, DT_S, segment.heading_rad)
        assert pose.theta == pytest.approx(segment.heading_rad, abs=ASSERT_TOL)
        # sin/cos of the heading leave only float noise, never a real cross-track offset.
        assert abs(segment.perpendicular_offset(pose.x, pose.y)) < 1e-12
    assert pose.y == pytest.approx(V_MAX_MPS * 60 * DT_S, abs=ASSERT_TOL)
