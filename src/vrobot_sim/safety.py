"""Forward-looking safety distance and circle-overlap fallback for circular obstacles."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence

from vrobot_sim.robot import EStopReason

if TYPE_CHECKING:
    from vrobot_sim.map_model import SegmentGeometry
    from vrobot_sim.obstacle_field import Obstacle
    from vrobot_sim.robot import Robot


class SafetyMonitor:
    """One tick of hazard judgement, made along the current segment centerline only."""

    def check(
        self,
        robot: Robot,
        obstacles: Sequence[Obstacle],
        segment: SegmentGeometry,
        dt: float,
        reference_v_mps: float | None = None,
    ) -> EStopReason:
        chassis = robot.spec.chassis
        x, y = robot.pose.x, robot.pose.y

        # Tangent circles are not an overlap, hence the strict comparisons throughout.
        for obstacle in obstacles:
            if math.hypot(obstacle.center_x - x, obstacle.center_y - y) < obstacle.radius_m + chassis.body_radius_m:
                return EStopReason.OVERLAP

        # A recovery check passes the speed the robot is about to take back: judging it at
        # its current zero speed would give it a braking distance of nothing at all.
        v = robot.v_mps if reference_v_mps is None else reference_v_mps
        lookahead_m = v * v / (2.0 * chassis.decel_max_mps2) + chassis.body_radius_m + v * dt
        start_m = min(max(segment.arc_position(x, y), 0.0), segment.length_m)
        # The window stops at the segment end: an obstacle belonging to the next segment
        # is that segment's problem, and this is what keeps an e-stop inside the segment.
        window_end_m = min(segment.length_m, start_m + lookahead_m)

        for obstacle in obstacles:
            reach_m = obstacle.radius_m + chassis.body_radius_m
            if abs(segment.perpendicular_offset(obstacle.center_x, obstacle.center_y)) > reach_m:
                continue
            center_m = segment.arc_position(obstacle.center_x, obstacle.center_y)
            if center_m - obstacle.radius_m <= window_end_m and center_m + obstacle.radius_m >= start_m:
                return EStopReason.SAFETY_DISTANCE
        return EStopReason.NONE
