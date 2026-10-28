"""Immutable per-tick state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vrobot_sim.robot import EStopReason, RobotStatus

if TYPE_CHECKING:
    from vrobot_sim.robot import Robot


@dataclass(frozen=True)
class RobotSnapshot:
    """The observable state of one robot at the end of a tick."""

    robot_id: str
    x_m: float
    y_m: float
    theta_rad: float
    v_mps: float
    omega_radps: float
    status: RobotStatus
    estop_reason: EStopReason

    @staticmethod
    def from_robot(robot: Robot) -> RobotSnapshot:
        return RobotSnapshot(
            robot_id=robot.robot_id,
            x_m=robot.pose.x,
            y_m=robot.pose.y,
            theta_rad=robot.pose.theta,
            v_mps=robot.v_mps,
            omega_radps=robot.omega_radps,
            status=robot.status,
            estop_reason=robot.estop_reason,
        )


@dataclass(frozen=True)
class TickSnapshot:
    """A consistent time slice over every robot, ordered by robot_id."""

    tick_index: int
    sim_time_s: float
    robots: tuple[RobotSnapshot, ...]
