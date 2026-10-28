"""Per-segment trapezoidal speed profile and in-place node turning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vrobot_sim.robot import ChassisConfig


@dataclass(frozen=True)
class TurnTarget:
    omega_radps: float
    aligned: bool


class Controller:
    """Turns the remaining distance or remaining angle into this tick's target speeds."""

    def __init__(self, chassis: ChassisConfig, dt: float):
        self._chassis = chassis
        self._dt = dt

    def linear_step(self, v_mps: float, remaining_m: float) -> float:
        """Target line speed for the linear sub-phase.

        ``arc_speed`` is the highest speed that still stops inside the remaining length
        at a_max, so the profile bends onto it instead of overshooting the segment end.
        The floor keeps a single step from dropping more than a_max times dt.
        """
        accel_step = self._chassis.a_max_mps2 * self._dt
        desired = min(self._chassis.v_max_mps, v_mps + accel_step)
        arc_speed = math.sqrt(2.0 * self._chassis.a_max_mps2 * max(0.0, remaining_m))
        return max(v_mps - accel_step, min(desired, arc_speed))

    def estop_step(self, v_mps: float) -> float:
        """Target line speed while stopping under the emergency deceleration limit."""
        return max(0.0, v_mps - self._chassis.decel_max_mps2 * self._dt)

    def segment_finished(self, remaining_m: float, v_mps: float) -> bool:
        return remaining_m <= self._chassis.arrival_tolerance_m and v_mps == 0.0

    def turn_step(self, turn_remaining_rad: float) -> TurnTarget:
        """Target angular speed for the turning sub-phase.

        Within the alignment tolerance the step covers the whole remaining angle, which
        is what lets the caller set theta to the exact segment heading in the same tick.
        """
        remaining = abs(turn_remaining_rad)
        deadbeat = remaining / self._dt
        limit = self._chassis.omega_max_radps
        magnitude = limit if deadbeat > limit else deadbeat
        sign = 1.0 if turn_remaining_rad >= 0.0 else -1.0
        return TurnTarget(
            omega_radps=sign * magnitude,
            aligned=remaining <= self._chassis.turn_align_tolerance_rad,
        )
