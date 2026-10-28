"""Active circular obstacle set with registration and deregistration checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RADIUS_RANGE_M = (0.0, 5.0)


@dataclass(frozen=True)
class Obstacle:
    obstacle_id: str
    center_x: float
    center_y: float
    radius_m: float


class ObstacleRejection(Enum):
    INVALID_RADIUS = "invalid_radius"
    DUPLICATE_ID = "duplicate_id"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ObstacleIntakeResult:
    """Accept or reject answer for IF-PROTO-obstacle-registration."""

    accepted: bool
    rejection: ObstacleRejection | None = None
    detail: str = ""


class ObstacleField:
    """Holds the obstacles in force. Rejected requests leave the set untouched."""

    def __init__(self, obstacles: tuple[Obstacle, ...] = ()):
        self._by_id: dict[str, Obstacle] = {item.obstacle_id: item for item in obstacles}

    def register(self, obstacle: Obstacle) -> ObstacleIntakeResult:
        low, high = RADIUS_RANGE_M
        if not low < obstacle.radius_m <= high:
            return ObstacleIntakeResult(
                accepted=False,
                rejection=ObstacleRejection.INVALID_RADIUS,
                detail=f"obstacle {obstacle.obstacle_id} radius_m={obstacle.radius_m} outside ({low}, {high}]",
            )
        if obstacle.obstacle_id in self._by_id:
            return ObstacleIntakeResult(
                accepted=False,
                rejection=ObstacleRejection.DUPLICATE_ID,
                detail=f"obstacle id {obstacle.obstacle_id} is already registered",
            )
        self._by_id[obstacle.obstacle_id] = obstacle
        return ObstacleIntakeResult(accepted=True)

    def deregister(self, obstacle_id: str) -> ObstacleIntakeResult:
        if obstacle_id not in self._by_id:
            return ObstacleIntakeResult(
                accepted=False,
                rejection=ObstacleRejection.NOT_FOUND,
                detail=f"obstacle id {obstacle_id} is not registered",
            )
        del self._by_id[obstacle_id]
        return ObstacleIntakeResult(accepted=True)

    def active(self) -> tuple[Obstacle, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))
