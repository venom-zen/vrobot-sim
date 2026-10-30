"""Right-of-way arbitration protocol: request, release and the synchronous answer."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class GrantOutcome(Enum):
    """Synchronous answer to one request; it carries no queue position or other state."""

    GRANTED = "granted"
    QUEUED = "queued"


@runtime_checkable
class RightOfWayArbiter(Protocol):
    """Consumer side of IF-PROTO-right-of-way-arbitration.

    A request is answered with the current outcome only; a queued request is granted
    later by the arbiter and read back by repeating the same call.
    """

    def request_right(
        self,
        robot_id: str,
        segment_index: int,
        zone_ids: tuple[str, ...],
        tick_index: int,
    ) -> GrantOutcome: ...

    def release_right(self, robot_id: str, zone_ids: tuple[str, ...]) -> None: ...
