"""SimulationDriver state machine, real-time advance and subscription tests."""

from __future__ import annotations

import asyncio
import json

import pytest
from vrobot_web.driver import SimulationDriver
from vrobot_web.scene import RobotConfig, SceneConfig, resolve_scene


class FakeSocket:
    """Stand-in for Starlette's WebSocket; records decoded JSON frames."""

    def __init__(self, slow: bool = False):
        self.frames: list[dict] = []
        self.closed = False
        self._slow = slow

    async def send_text(self, data: str) -> None:
        if self._slow:
            await asyncio.sleep(10.0)
        self.frames.append(json.loads(data))

    async def close(self) -> None:
        self.closed = True


def _config() -> SceneConfig:
    return SceneConfig(
        robots=[RobotConfig(robot_id="R1", start_node_id="N01", target_node_id="N03")]
    )


def _scene():
    return resolve_scene(_config()).scenario


def _tick_count(socket: FakeSocket) -> int:
    return sum(1 for frame in socket.frames if frame["kind"] == "tick")


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition was not met in time")
        await asyncio.sleep(0.005)


def _index_of(socket: FakeSocket, kind: str, mode: str | None = None) -> int:
    for index, frame in enumerate(socket.frames):
        if frame["kind"] == kind and (mode is None or frame.get("mode") == mode):
            return index
    raise AssertionError(f"no {kind} frame with mode={mode} in {socket.frames}")


def test_apply_publishes_tick_zero_to_a_new_subscriber():
    async def scenario() -> None:
        driver = SimulationDriver()
        try:
            driver.apply_scene(_scene())
            assert driver.mode == "configured"
            snapshot = driver.latest_snapshot
            assert snapshot.tick_index == 0
            assert snapshot.sim_time_s == pytest.approx(0.02)

            socket = FakeSocket()
            driver.subscribe(socket)
            await _wait_for(lambda: len(socket.frames) == 1)
            frame = socket.frames[0]
            assert frame["kind"] == "status"
            assert frame["mode"] == "configured"
            assert frame["snapshot"]["tick_index"] == 0
            assert [robot["robot_id"] for robot in frame["snapshot"]["robots"]] == ["R1"]
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_pause_freezes_ticks_and_resume_continues_from_the_paused_tick():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005)
        try:
            driver.apply_scene(_scene())
            socket = FakeSocket()
            driver.subscribe(socket)
            await _wait_for(lambda: len(socket.frames) == 1)

            assert driver.control("start").accepted
            await _wait_for(lambda: driver.latest_snapshot.tick_index >= 3)

            assert driver.control("pause").accepted
            assert driver.mode == "paused"
            frozen = driver.latest_snapshot.tick_index
            await _wait_for(
                lambda: any(
                    frame["kind"] == "status" and frame["mode"] == "paused"
                    for frame in socket.frames
                )
            )
            paused_at = _index_of(socket, "status", "paused")
            await asyncio.sleep(0.05)
            assert driver.latest_snapshot.tick_index == frozen
            assert all(
                frame["kind"] != "tick" for frame in socket.frames[paused_at + 1 :]
            )

            assert driver.control("resume").accepted
            assert driver.mode == "running"
            await _wait_for(lambda: driver.latest_snapshot.tick_index > frozen)
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_reset_returns_to_tick_zero_and_keeps_the_last_scene():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005)
        try:
            driver.apply_scene(_scene())
            assert driver.control("start").accepted
            await _wait_for(lambda: driver.latest_snapshot.tick_index >= 2)

            assert driver.control("reset").accepted
            assert driver.mode == "configured"
            assert driver.latest_snapshot.tick_index == 0
            assert [robot.robot_id for robot in driver.latest_snapshot.robots] == ["R1"]

            assert driver.control("start").accepted
            await _wait_for(lambda: driver.latest_snapshot.tick_index >= 2)
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_actions_outside_the_state_machine_are_rejected_without_changes():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005)
        try:
            for action in ("start", "pause", "resume", "reset"):
                outcome = driver.control(action)
                assert not outcome.accepted
                assert outcome.violations
                assert driver.mode == "unconfigured"

            driver.apply_scene(_scene())
            assert driver.control("start").accepted
            assert not driver.control("start").accepted
            assert not driver.control("resume").accepted
            assert driver.mode == "running"

            assert driver.control("pause").accepted
            assert not driver.control("pause").accepted
            assert not driver.control("start").accepted
            assert driver.mode == "paused"

            assert driver.control("resume").accepted
            assert not driver.control("resume").accepted
            assert driver.mode == "running"
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_default_cadence_matches_the_scenario_step():
    """The 1x playback rate depends on the cadence and the kernel step agreeing."""
    assert SimulationDriver()._dt_s == resolve_scene(_config()).scenario.dt_s


def test_slow_subscriber_times_out_and_is_removed_while_others_keep_receiving():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005, send_timeout_s=0.05)
        try:
            driver.apply_scene(_scene())
            slow = FakeSocket(slow=True)
            driver.subscribe(slow)
            await _wait_for(lambda: len(driver._subscribers) == 0)
            assert slow.closed

            fast = FakeSocket()
            driver.subscribe(fast)
            assert driver.control("start").accepted
            await _wait_for(
                lambda: len([frame for frame in fast.frames if frame["kind"] == "tick"]) >= 3
            )
            assert driver.mode == "running"
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_slow_subscriber_does_not_stall_ticks_while_its_send_is_pending():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005)
        try:
            driver.apply_scene(_scene())
            fast = FakeSocket()
            driver.subscribe(fast)
            assert driver.control("start").accepted
            await _wait_for(lambda: _tick_count(fast) >= 2)
            ticks_before = _tick_count(fast)

            slow = FakeSocket(slow=True)
            driver.subscribe(slow)
            assert slow in driver._subscribers
            await _wait_for(lambda: _tick_count(fast) >= ticks_before + 3)
            # The slow send is still pending here; ticks reached the fast socket anyway.
            assert slow in driver._subscribers

            await _wait_for(lambda: slow not in driver._subscribers)
            assert slow.closed
            assert slow.frames == []
            assert fast in driver._subscribers
        finally:
            await driver.shutdown()

    asyncio.run(scenario())


def test_reconnect_receives_current_mode_and_latest_snapshot():
    async def scenario() -> None:
        driver = SimulationDriver(dt_s=0.005)
        try:
            driver.apply_scene(_scene())
            first = FakeSocket()
            driver.subscribe(first)
            assert driver.control("start").accepted
            await _wait_for(lambda: driver.latest_snapshot.tick_index >= 5)
            driver.unsubscribe(first)

            reconnect = FakeSocket()
            expected = driver.latest_snapshot.tick_index
            driver.subscribe(reconnect)
            await _wait_for(lambda: len(reconnect.frames) >= 1)
            frame = reconnect.frames[0]
            assert frame["kind"] == "status"
            assert frame["mode"] == "running"
            assert frame["snapshot"]["tick_index"] >= expected
        finally:
            await driver.shutdown()

    asyncio.run(scenario())
