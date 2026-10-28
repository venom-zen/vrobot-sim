"""Scenario configuration object and creation-time validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from vrobot_sim.map_model import TopologyMap, VEHICLE_CLASS_TAGS
from vrobot_sim.maps import BUILT_IN_MAP_IDS
from vrobot_sim.obstacle_field import Obstacle, RADIUS_RANGE_M
from vrobot_sim.robot import ChassisConfig, RobotSpec

DT_RANGE_S = (0.0, 0.05)

CHASSIS_RANGES_MPS = {
    "v_max_mps": (0.0, 3.0),
    "a_max_mps2": (0.0, 2.0),
    "decel_max_mps2": (0.0, 3.0),
    "omega_max_radps": (0.0, 3.0),
    "body_radius_m": (0.0, 2.0),
}
TOLERANCE_FIELDS = ("turn_align_tolerance_rad", "arrival_tolerance_m")


class ScenarioValidationError(ValueError):
    """Raised when scenario configuration fails creation-time validation."""

    def __init__(self, violations: Sequence[str]):
        self.violations = tuple(violations)
        super().__init__("scenario validation failed: " + "; ".join(self.violations))


@dataclass(frozen=True)
class Scenario:
    map_id: str
    dt_s: float = 0.02
    robots: tuple[RobotSpec, ...] = ()
    obstacles: tuple[Obstacle, ...] = ()

    def validate(self, topology_map: TopologyMap | None = None) -> list[str]:
        """List every violation. Map-dependent checks run only when a map is supplied."""
        violations: list[str] = []
        self._validate_map_id(violations)
        self._validate_dt(violations)
        self._validate_robots(violations, topology_map)
        self._validate_obstacles(violations)
        return violations

    def _validate_map_id(self, violations: list[str]) -> None:
        if self.map_id not in BUILT_IN_MAP_IDS:
            violations.append(f"map_id={self.map_id!r} is not one of {sorted(BUILT_IN_MAP_IDS)}")

    def _validate_dt(self, violations: list[str]) -> None:
        low, high = DT_RANGE_S
        if not low < self.dt_s <= high:
            violations.append(f"dt_s={self.dt_s} outside ({low}, {high}]")

    def _validate_robots(self, violations: list[str], topology_map: TopologyMap | None) -> None:
        seen_ids: set[str] = set()
        for spec in self.robots:
            if spec.robot_id in seen_ids:
                violations.append(f"duplicate robot id {spec.robot_id}")
            seen_ids.add(spec.robot_id)

            if spec.vehicle_class not in VEHICLE_CLASS_TAGS:
                violations.append(
                    f"robot {spec.robot_id} vehicle_class={spec.vehicle_class!r} outside {sorted(VEHICLE_CLASS_TAGS)}"
                )
            self._validate_chassis(violations, spec)
            self._validate_planned_path(violations, spec, topology_map)

    def _validate_chassis(self, violations: list[str], spec: RobotSpec) -> None:
        for name, (low, high) in CHASSIS_RANGES_MPS.items():
            value = getattr(spec.chassis, name)
            if not low < value < high:
                violations.append(f"robot {spec.robot_id} chassis {name}={value} outside ({low}, {high})")
        for name in TOLERANCE_FIELDS:
            value = getattr(spec.chassis, name)
            if value < 0.0 or not math.isfinite(value):
                violations.append(f"robot {spec.robot_id} chassis {name}={value} must be a finite non-negative number")
        self._validate_turn_tolerance(violations, spec)

    def _validate_turn_tolerance(self, violations: list[str], spec: RobotSpec) -> None:
        low, _ = DT_RANGE_S
        if not low < self.dt_s:
            return
        chassis: ChassisConfig = spec.chassis
        ratio = chassis.turn_align_tolerance_rad / self.dt_s
        if ratio > chassis.omega_max_radps:
            violations.append(
                f"robot {spec.robot_id} turn_align_tolerance_rad={chassis.turn_align_tolerance_rad} over "
                f"dt_s={self.dt_s} gives {ratio} rad/s above omega_max_radps={chassis.omega_max_radps}"
            )

    def _validate_planned_path(
        self, violations: list[str], spec: RobotSpec, topology_map: TopologyMap | None
    ) -> None:
        if len(spec.planned_node_path) < 2:
            violations.append(
                f"robot {spec.robot_id} planned_node_path={list(spec.planned_node_path)} names fewer than two nodes"
            )
        if spec.planned_node_path and spec.planned_node_path[0] != spec.start_node_id:
            violations.append(
                f"robot {spec.robot_id} planned_node_path starts at {spec.planned_node_path[0]} "
                f"while start_node_id is {spec.start_node_id}"
            )
        if topology_map is not None and spec.start_node_id not in {node.node_id for node in topology_map.nodes}:
            violations.append(
                f"robot {spec.robot_id} start_node_id={spec.start_node_id} is not in map {topology_map.map_id}"
            )

    def _validate_obstacles(self, violations: list[str]) -> None:
        low, high = RADIUS_RANGE_M
        seen_ids: set[str] = set()
        for obstacle in self.obstacles:
            if obstacle.obstacle_id in seen_ids:
                violations.append(f"duplicate obstacle id {obstacle.obstacle_id}")
            seen_ids.add(obstacle.obstacle_id)
            if not low < obstacle.radius_m <= high:
                violations.append(
                    f"obstacle {obstacle.obstacle_id} radius_m={obstacle.radius_m} outside ({low}, {high}]"
                )
