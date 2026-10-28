"""Differential-drive pose integration: the only v/omega to x/y/theta mapping."""

from __future__ import annotations

import math
from dataclasses import dataclass

FULL_TURN_RAD = 2.0 * math.pi


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    theta: float


def normalize_theta(theta: float) -> float:
    """Fold an angle into [-pi, pi); pi itself lands on -pi."""
    return (theta + math.pi) % FULL_TURN_RAD - math.pi


def advance_pose(pose: Pose, v: float, omega: float, dt: float, segment_heading: float) -> Pose:
    """Integrate one step.

    A zero angular speed means the linear sub-phase, where the displacement follows the
    segment direction and theta is pinned to it; a non-zero angular speed means an
    in-place turn, where the body does not translate.
    """
    if omega == 0.0:
        step_m = v * dt
        return Pose(
            pose.x + step_m * math.cos(segment_heading),
            pose.y + step_m * math.sin(segment_heading),
            normalize_theta(segment_heading),
        )
    return Pose(pose.x, pose.y, normalize_theta(pose.theta + omega * dt))
