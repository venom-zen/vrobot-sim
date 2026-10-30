"""Asyncio real-time driver: advance the kernel at 50 tick/s and broadcast frames.

The driver owns the single ``Simulation`` behind the web UI. Transitions and frame
enqueues run on the event loop without locks. Each subscriber has its own queue and
sender task, so one slow browser cannot stall the tick loop or the other subscribers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation
from vrobot_sim.snapshots import TickSnapshot
from vrobot_web.scene import SCENE_DT_S
from vrobot_web.schemas import SnapshotPayload, StatusFrame, TickFrame

SEND_TIMEOUT_S = 1.0

UNCONFIGURED = "unconfigured"
CONFIGURED = "configured"
RUNNING = "running"
PAUSED = "paused"

_CONTROL_ACTIONS = ("start", "pause", "resume", "reset")


class StateSocket(Protocol):
    """The WebSocket operations the driver needs; Starlette's WebSocket satisfies it."""

    async def send_text(self, data: str) -> None: ...

    async def close(self) -> None: ...


@dataclass
class _Subscriber:
    socket: StateSocket
    queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None


@dataclass(frozen=True)
class ControlOutcome:
    """The driver's answer to one control action."""

    accepted: bool
    violations: tuple[str, ...] = ()


class SimulationDriver:
    """One kernel instance, one run mode and the set of live state subscribers."""

    def __init__(self, dt_s: float = SCENE_DT_S, send_timeout_s: float = SEND_TIMEOUT_S):
        self._dt_s = dt_s
        self._send_timeout_s = send_timeout_s
        self._scenario: Scenario | None = None
        self._simulation: Simulation | None = None
        self._snapshot: TickSnapshot | None = None
        self._mode = UNCONFIGURED
        self._advance_task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._subscribers: dict[StateSocket, _Subscriber] = {}

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def latest_snapshot(self) -> TickSnapshot | None:
        return self._snapshot

    # -- scene lifecycle -------------------------------------------------

    def apply_scene(self, scenario: Scenario) -> None:
        """Build a fresh simulation and publish tick 0; may raise the kernel's error unturned."""
        simulation = Simulation.create_scheduled(scenario)
        snapshot = simulation.step()
        self._replace_simulation(scenario, simulation, snapshot)

    def reset(self) -> ControlOutcome:
        if self._scenario is None:
            return ControlOutcome(False, ("reset requires an applied scene",))
        simulation = Simulation.create_scheduled(self._scenario)
        snapshot = simulation.step()
        self._replace_simulation(self._scenario, simulation, snapshot)
        return ControlOutcome(True)

    def _replace_simulation(
        self, scenario: Scenario, simulation: Simulation, snapshot: TickSnapshot
    ) -> None:
        self._stop_advance_task()
        self._scenario = scenario
        self._simulation = simulation
        self._snapshot = snapshot
        self._mode = CONFIGURED
        self._broadcast_status()

    # -- control state machine -------------------------------------------

    def control(self, action: str) -> ControlOutcome:
        if action not in _CONTROL_ACTIONS:
            return ControlOutcome(False, (f"unknown control action {action!r}",))
        if action == "start":
            return self._start()
        if action == "pause":
            return self._pause()
        if action == "resume":
            return self._resume()
        return self.reset()

    def _start(self) -> ControlOutcome:
        if self._mode != CONFIGURED:
            return self._reject("start")
        simulation = self._simulation
        self._mode = RUNNING
        self._advance_task = asyncio.create_task(self._advance(simulation), name="vrobot-advance")
        self._broadcast_status()
        return ControlOutcome(True)

    def _pause(self) -> ControlOutcome:
        if self._mode != RUNNING:
            return self._reject("pause")
        self._mode = PAUSED
        self._wake.clear()
        self._broadcast_status()
        return ControlOutcome(True)

    def _resume(self) -> ControlOutcome:
        if self._mode != PAUSED:
            return self._reject("resume")
        self._mode = RUNNING
        self._wake.set()
        self._broadcast_status()
        return ControlOutcome(True)

    def _reject(self, action: str) -> ControlOutcome:
        return ControlOutcome(
            False, (f"action {action!r} is not allowed in mode {self._mode!r}",)
        )

    # -- real-time advance -----------------------------------------------

    async def _advance(self, simulation: Simulation) -> None:
        """Step every dt until the mode leaves ``running``; a tick never crosses a pause."""
        loop = asyncio.get_running_loop()
        deadline = loop.time()
        while True:
            if self._mode != RUNNING:
                await self._wake.wait()
                self._wake.clear()
                deadline = loop.time()
                continue
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            if self._mode != RUNNING:
                continue
            snapshot = simulation.step()
            self._snapshot = snapshot
            self._enqueue_tick(snapshot)
            deadline += self._dt_s

    def _stop_advance_task(self) -> None:
        task = self._advance_task
        self._advance_task = None
        self._wake.clear()
        if task is not None and not task.done():
            task.cancel()

    # -- subscriptions ---------------------------------------------------

    def subscribe(self, socket: StateSocket) -> None:
        """Register a connection and queue its first ``StatusFrame``."""
        subscriber = _Subscriber(socket)
        subscriber.queue.put_nowait(self._status_text())
        self._subscribers[socket] = subscriber
        subscriber.task = asyncio.create_task(self._pump(subscriber), name="vrobot-send")

    def unsubscribe(self, socket: StateSocket) -> None:
        subscriber = self._subscribers.pop(socket, None)
        if subscriber is not None and subscriber.task is not None:
            subscriber.task.cancel()

    async def _pump(self, subscriber: _Subscriber) -> None:
        while True:
            text = await subscriber.queue.get()
            try:
                await asyncio.wait_for(subscriber.socket.send_text(text), self._send_timeout_s)
            except Exception:
                await self._drop(subscriber)
                return

    async def _drop(self, subscriber: _Subscriber) -> None:
        self._subscribers.pop(subscriber.socket, None)
        try:
            await subscriber.socket.close()
        except Exception:
            pass

    async def shutdown(self) -> None:
        self._stop_advance_task()
        for subscriber in list(self._subscribers.values()):
            self._subscribers.pop(subscriber.socket, None)
            if subscriber.task is not None:
                subscriber.task.cancel()
            try:
                await subscriber.socket.close()
            except Exception:
                pass

    # -- frames ----------------------------------------------------------

    def _status_text(self) -> str:
        snapshot = (
            SnapshotPayload.from_tick(self._snapshot) if self._snapshot is not None else None
        )
        return StatusFrame(mode=self._mode, snapshot=snapshot).model_dump_json()

    def _broadcast_status(self) -> None:
        text = self._status_text()
        for subscriber in list(self._subscribers.values()):
            subscriber.queue.put_nowait(text)

    def _enqueue_tick(self, snapshot: TickSnapshot) -> None:
        text = TickFrame(snapshot=SnapshotPayload.from_tick(snapshot)).model_dump_json()
        for subscriber in list(self._subscribers.values()):
            subscriber.queue.put_nowait(text)
