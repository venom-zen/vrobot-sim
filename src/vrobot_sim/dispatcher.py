"""Built-in FCFS dispatcher: route assignment, right-of-way arbitration, zone state.

The dispatcher is the single owner of per-zone holders and queues for one simulation.
Grants are settled only in :meth:`FcfsDispatcher.dispatch`, so a request made during a
robot advance takes effect no earlier than the next dispatch phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.rights import GrantOutcome, RightOfWayArbiter
from vrobot_sim.robot import CommandKind, CommandSource, MotionCommand, Robot, RobotSpec, RobotStatus
from vrobot_sim.snapshots import ZoneSnapshot


@runtime_checkable
class ZoneStateProvider(Protocol):
    """Producer side of IF-PROTO-zone-state-read: every map zone, sorted by zone_id."""

    def read_zone_state(self) -> tuple[ZoneSnapshot, ...]: ...


@runtime_checkable
class ScheduledDispatcher(CommandSource, RightOfWayArbiter, ZoneStateProvider, Protocol):
    """The three roles ``create_scheduled`` injects as one object."""


@dataclass
class _Request:
    """One application for the zones of a segment; keyed by (robot_id, segment_index)."""

    robot_id: str
    segment_index: int
    zone_ids: tuple[str, ...]
    arrival_tick: int
    granted: bool = False

    @property
    def arrival_order(self) -> tuple[int, str]:
        return (self.arrival_tick, self.robot_id)


class FcfsDispatcher:
    """First-come-first-served arbitration with capacity limits and atomic multi-zone grants."""

    def __init__(self, specs: Sequence[RobotSpec], topology_map: TopologyMap):
        self._specs = tuple(specs)
        self._zone_ids = tuple(sorted(zone.zone_id for zone in topology_map.zones))
        self._capacity = {zone.zone_id: zone.capacity for zone in topology_map.zones}
        self._holders: dict[str, set[str]] = {zone_id: set() for zone_id in self._zone_ids}
        self._requests: dict[tuple[str, int], _Request] = {}

    def request_right(
        self,
        robot_id: str,
        segment_index: int,
        zone_ids: tuple[str, ...],
        tick_index: int,
    ) -> GrantOutcome:
        """Record the application once; repeats return the current outcome unchanged."""
        key = (robot_id, segment_index)
        request = self._requests.get(key)
        if request is None:
            request = _Request(robot_id, segment_index, tuple(zone_ids), tick_index)
            self._requests[key] = request
        return GrantOutcome.GRANTED if request.granted else GrantOutcome.QUEUED

    def release_right(self, robot_id: str, zone_ids: tuple[str, ...]) -> None:
        """Drop held zones; releasing a zone the robot does not hold is a no-op."""
        released = set(zone_ids)
        for zone_id in released:
            self._holders[zone_id].discard(robot_id)
        for key in tuple(self._requests):
            request = self._requests[key]
            if request.robot_id == robot_id and request.granted and released.issuperset(request.zone_ids):
                del self._requests[key]

    def read_zone_state(self) -> tuple[ZoneSnapshot, ...]:
        return tuple(
            ZoneSnapshot(
                zone_id=zone_id,
                capacity=self._capacity[zone_id],
                holder_robot_ids=tuple(sorted(self._holders[zone_id])),
                waiting_robot_ids=tuple(request.robot_id for request in self._waiting_for(zone_id)),
            )
            for zone_id in self._zone_ids
        )

    def dispatch(self, tick_index: int, robots: Sequence[Robot]) -> None:
        """Settle grants, then assign paths at start_tick, then resume every e-stopped robot."""
        self._grant_pending()
        targets = {robot.robot_id: robot for robot in robots}
        for spec in self._specs:
            if spec.start_tick == tick_index:
                targets[spec.robot_id].receive(
                    MotionCommand(
                        kind=CommandKind.ASSIGN_PATH,
                        robot_id=spec.robot_id,
                        node_path=spec.planned_node_path,
                    )
                )
        for robot in robots:
            if robot.status is RobotStatus.E_STOP:
                robot.receive(MotionCommand(kind=CommandKind.RESUME, robot_id=robot.robot_id))

    def _grant_pending(self) -> None:
        waiting = sorted(
            (request for request in self._requests.values() if not request.granted),
            key=lambda item: item.arrival_order,
        )
        for request in waiting:
            if not self._is_first_in_every_queue(request):
                continue
            if not all(
                len(self._holders[zone_id]) < self._capacity[zone_id] for zone_id in request.zone_ids
            ):
                continue
            request.granted = True
            for zone_id in request.zone_ids:
                self._holders[zone_id].add(request.robot_id)

    def _is_first_in_every_queue(self, request: _Request) -> bool:
        return all(self._waiting_for(zone_id)[0] is request for zone_id in request.zone_ids)

    def _waiting_for(self, zone_id: str) -> tuple[_Request, ...]:
        waiting = [
            request
            for request in self._requests.values()
            if not request.granted and zone_id in request.zone_ids
        ]
        return tuple(sorted(waiting, key=lambda item: item.arrival_order))
