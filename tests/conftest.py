"""Shared fixtures, the default chassis parameters declared in design.md and run helpers."""

from __future__ import annotations

from typing import Sequence

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.obstacle_field import Obstacle, ObstacleField
from vrobot_sim.robot import (
    ChassisConfig,
    CommandKind,
    EStopReason,
    MotionCommand,
    Robot,
    RobotSpec,
    RobotStatus,
)
from vrobot_sim.safety import SafetyMonitor

V_MAX_MPS = 1.5
A_MAX_MPS2 = 0.8
DECEL_MAX_MPS2 = 1.5
OMEGA_MAX_RADPS = 1.2
BODY_RADIUS_M = 0.35
TURN_ALIGN_TOLERANCE_RAD = 0.02
ARRIVAL_TOLERANCE_M = 0.02
DT_S = 0.02

# Tolerance applied to every "does not exceed the configured limit" assertion.
ASSERT_TOL = 1e-9

DEFAULT_SPEC_ID = "R1"


def make_spec(
    path: Sequence[str] = ("N01", "N02"),
    start_node_id: str = "N01",
    start_theta_rad: float = 0.0,
    robot_id: str = DEFAULT_SPEC_ID,
    chassis: ChassisConfig | None = None,
    vehicle_class: str = "AMR-500",
    start_tick: int = 0,
) -> RobotSpec:
    return RobotSpec(
        robot_id=robot_id,
        chassis=chassis or ChassisConfig(),
        vehicle_class=vehicle_class,
        start_node_id=start_node_id,
        start_theta_rad=start_theta_rad,
        planned_node_path=tuple(path),
        start_tick=start_tick,
    )


def make_robot(
    topology_map: TopologyMap,
    spec: RobotSpec | None = None,
    dt: float = DT_S,
    obstacles: ObstacleField | None = None,
) -> Robot:
    return Robot(
        spec or make_spec(),
        topology_map,
        dt,
        SafetyMonitor(),
        obstacles if obstacles is not None else ObstacleField(),
    )


def make_obstacle_field(obstacles: Sequence[Obstacle] = ()) -> ObstacleField:
    return ObstacleField(tuple(obstacles))


def obstacle_at(center_x: float, center_y: float, radius_m: float = 0.2, obstacle_id: str = "OBS") -> Obstacle:
    return Obstacle(obstacle_id, center_x, center_y, radius_m)


def read_state(robot: Robot) -> tuple[float, float, float, float, float, RobotStatus, EStopReason]:
    """The observable state a snapshot exposes for one robot."""
    return (
        robot.pose.x,
        robot.pose.y,
        robot.pose.theta,
        robot.v_mps,
        robot.omega_radps,
        robot.status,
        robot.estop_reason,
    )


class ScriptedCommandSource:
    """Stand-in producer for IF-PROTO-robot-command-intake over a fixed schedule."""

    def __init__(self, schedule):
        self._schedule = tuple(schedule)

    def dispatch(self, tick_index: int, robots) -> None:
        targets = {robot.robot_id: robot for robot in robots}
        for tick, command in self._schedule:
            if tick == tick_index:
                targets[command.robot_id].receive(command)


def assign_path(robot_id: str, path: tuple[str, ...]) -> MotionCommand:
    return MotionCommand(kind=CommandKind.ASSIGN_PATH, robot_id=robot_id, node_path=path)


def resume(robot_id: str) -> MotionCommand:
    return MotionCommand(kind=CommandKind.RESUME, robot_id=robot_id)
