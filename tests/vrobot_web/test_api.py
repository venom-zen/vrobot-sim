"""HTTP and WebSocket contract tests against the real application."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from vrobot_sim.map_model import EdgeDirection, MapEdge, MapNode, build_topology_map
from vrobot_sim.scenario import ScenarioValidationError
from vrobot_sim.simulation import Simulation

from vrobot_web.app import create_app
from vrobot_web.scene import SceneConfig, resolve_scene

# N03 exists but is not reachable from N01: the only edge joins N01 and N02.
PARTIAL_MAP = build_topology_map(
    "partial",
    (MapNode("N01", 0.0, 0.0), MapNode("N02", 20.0, 0.0), MapNode("N03", 40.0, 0.0)),
    (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),),
)

RING_ROBOTS = [
    {"robot_id": "R1", "start_node_id": "N01", "waypoints": ["N02"], "target_node_id": "N03"},
    {"robot_id": "R2", "start_node_id": "N02", "waypoints": ["N03"], "target_node_id": "N01"},
    {"robot_id": "R3", "start_node_id": "N03", "waypoints": ["N01"], "target_node_id": "N02"},
]


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _robot(robot_id: str = "R1", start: str = "N01", waypoints=None, target: str = "N03") -> dict:
    return {
        "robot_id": robot_id,
        "start_node_id": start,
        "waypoints": list(waypoints or []),
        "target_node_id": target,
    }


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition was not met in time")
        time.sleep(0.01)


def _assert_snapshot_matches(payload: dict, kernel) -> None:
    assert payload["tick_index"] == kernel.tick_index
    assert payload["sim_time_s"] == kernel.sim_time_s
    assert [robot["robot_id"] for robot in payload["robots"]] == [
        robot.robot_id for robot in kernel.robots
    ]
    for actual, expected in zip(payload["robots"], kernel.robots):
        assert actual == {
            "robot_id": expected.robot_id,
            "x_m": expected.x_m,
            "y_m": expected.y_m,
            "theta_rad": expected.theta_rad,
            "v_mps": expected.v_mps,
            "omega_radps": expected.omega_radps,
            "status": expected.status.value,
            "estop_reason": expected.estop_reason.value,
        }
    assert [zone["zone_id"] for zone in payload["zones"]] == [
        zone.zone_id for zone in kernel.zones
    ]
    for actual, expected in zip(payload["zones"], kernel.zones):
        assert actual == {
            "zone_id": expected.zone_id,
            "capacity": expected.capacity,
            "holder_robot_ids": list(expected.holder_robot_ids),
            "waiting_robot_ids": list(expected.waiting_robot_ids),
        }


def test_map_read_returns_the_demo_topology(client):
    response = client.get("/api/map")
    assert response.status_code == 200
    payload = response.json()
    assert payload["map_id"] == "demo"
    assert len(payload["nodes"]) == 10
    assert len(payload["edges"]) == 11
    assert len(payload["zones"]) == 5
    edges = {edge["edge_id"]: edge for edge in payload["edges"]}
    assert edges["E02"]["direction"] == "fwd"
    assert edges["E03"]["direction"] == "both"
    zones = {zone["zone_id"]: zone for zone in payload["zones"]}
    assert zones["Z04"]["edge_ids"] == ["E04", "E05"]
    assert zones["Z05"]["capacity"] == 1


def test_map_load_failure_returns_500(client, monkeypatch):
    def _broken(map_id: str):
        raise RuntimeError("demo map data is corrupt")

    monkeypatch.setattr("vrobot_web.app.load_map", _broken)
    response = client.get("/api/map")
    assert response.status_code == 500
    assert response.json() == {"violations": ["demo map data is corrupt"]}


def test_scene_apply_returns_paths_and_tick_zero(client):
    body = {"robots": RING_ROBOTS}
    response = client.put("/api/scene", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "configured"
    assert payload["resolved_paths"] == {
        "R1": ["N01", "N02", "N03"],
        "R2": ["N02", "N03", "N01"],
        "R3": ["N03", "N01", "N02"],
    }
    kernel = Simulation.create_scheduled(
        resolve_scene(SceneConfig.model_validate(body)).scenario
    ).step()
    _assert_snapshot_matches(payload["snapshot"], kernel)


def test_scene_rejection_keeps_the_driver_untouched(client):
    response = client.put("/api/scene", json={"robots": [_robot()]})
    assert response.status_code == 200
    driver = client.app.state.driver
    assert client.post("/api/control", json={"action": "start"}).status_code == 200
    _wait_until(lambda: driver.latest_snapshot.tick_index >= 2)
    before = driver.latest_snapshot.tick_index

    response = client.put("/api/scene", json={"robots": [_robot("R1", target="N01")]})
    assert response.status_code == 422
    assert driver.mode == "running"
    _wait_until(lambda: driver.latest_snapshot.tick_index > before)


@pytest.mark.parametrize(
    ("robots", "fragment"),
    [
        ([_robot("R1", "N01", target="N02"), _robot("R2", "N01", target="N03")], "shares start node N01"),
        ([], "robot count 0 is outside 1-10"),
        ([_robot(f"R{i}", "N01", target="N02") for i in range(11)], "robot count 11 is outside 1-10"),
        ([_robot("R1", "N01", target="N01")], "start_node_id equals target_node_id N01"),
        ([_robot("R1", "N01", ["N01"], "N03")], "anchor chain repeats node N01"),
        ([_robot("R1", "N99", target="N03")], "anchor N99 is not in map demo"),
        ([_robot("R1", "N01", target="N02"), _robot("R1", "N03", target="N01")], "duplicate robot_id"),
    ],
)
def test_invalid_scene_returns_422_without_building(client, robots, fragment):
    response = client.put("/api/scene", json={"robots": robots})
    assert response.status_code == 422
    violations = response.json()["violations"]
    assert any(fragment in message for message in violations)
    driver = client.app.state.driver
    assert driver.mode == "unconfigured"
    assert driver.latest_snapshot is None


def test_unreachable_route_is_rejected_with_422(client, monkeypatch):
    monkeypatch.setattr("vrobot_web.scene.load_map", lambda map_id: PARTIAL_MAP)
    response = client.put("/api/scene", json={"robots": [_robot("R1", "N01", target="N03")]})
    assert response.status_code == 422
    assert any("no route from N01 to N03" in message for message in response.json()["violations"])
    assert client.app.state.driver.mode == "unconfigured"


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        '{"robots": "not a list"}',
        '{"robots": [{"robot_id": "R1", "start_node_id": "N01"}]}',
        '{"robots": [{"robot_id": 1, "start_node_id": "N01", "target_node_id": "N03"}]}',
    ],
)
def test_unparseable_scene_body_returns_422(client, content):
    response = client.put(
        "/api/scene", content=content, headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["violations"]
    assert client.app.state.driver.mode == "unconfigured"


def test_kernel_rejection_is_reported_as_422(client, monkeypatch):
    def _reject(scenario, dispatcher=None):
        raise ScenarioValidationError(["kernel rejected the scene"])

    monkeypatch.setattr(Simulation, "create_scheduled", staticmethod(_reject))
    response = client.put("/api/scene", json={"robots": [_robot()]})
    assert response.status_code == 422
    assert "kernel rejected the scene" in response.json()["violations"]
    assert client.app.state.driver.mode == "unconfigured"


def test_control_state_machine(client):
    driver = client.app.state.driver
    response = client.post("/api/control", json={"action": "start"})
    assert response.status_code == 409
    assert response.json()["mode"] == "unconfigured"
    assert response.json()["violations"]

    assert client.put("/api/scene", json={"robots": [_robot()]}).status_code == 200
    for action in ("pause", "resume"):
        response = client.post("/api/control", json={"action": action})
        assert response.status_code == 409
        assert response.json()["mode"] == "configured"

    response = client.post("/api/control", json={"action": "start"})
    assert response.status_code == 200
    assert response.json()["mode"] == "running"
    _wait_until(lambda: driver.latest_snapshot.tick_index >= 2)
    assert client.post("/api/control", json={"action": "start"}).status_code == 409
    assert client.post("/api/control", json={"action": "resume"}).status_code == 409

    response = client.post("/api/control", json={"action": "pause"})
    assert response.status_code == 200
    assert response.json()["mode"] == "paused"
    frozen = driver.latest_snapshot.tick_index
    time.sleep(0.1)
    assert driver.latest_snapshot.tick_index == frozen

    response = client.post("/api/control", json={"action": "resume"})
    assert response.status_code == 200
    assert response.json()["mode"] == "running"
    _wait_until(lambda: driver.latest_snapshot.tick_index > frozen)

    response = client.post("/api/control", json={"action": "reset"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "configured"
    assert payload["snapshot"]["tick_index"] == 0
    assert driver.latest_snapshot.tick_index == 0
    assert client.post("/api/control", json={"action": "pause"}).status_code == 409


@pytest.mark.parametrize(
    "content",
    ['{"action": "jump"}', "{}", '{"action": null}', "{oops"],
)
def test_invalid_control_body_returns_422(client, content):
    response = client.post(
        "/api/control", content=content, headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["violations"]
    assert client.app.state.driver.mode == "unconfigured"


def test_applying_a_scene_while_running_returns_to_tick_zero(client):
    driver = client.app.state.driver
    assert client.put("/api/scene", json={"robots": [_robot()]}).status_code == 200
    assert client.post("/api/control", json={"action": "start"}).status_code == 200
    _wait_until(lambda: driver.latest_snapshot.tick_index >= 2)

    response = client.put("/api/scene", json={"robots": [_robot("R9", "N08", target="N10")]})
    assert response.status_code == 200
    assert response.json()["mode"] == "configured"
    assert response.json()["snapshot"]["tick_index"] == 0
    time.sleep(0.1)
    assert driver.latest_snapshot.tick_index == 0


def test_websocket_initial_frame_reports_unconfigured(client):
    with client.websocket_connect("/ws/state") as websocket:
        assert websocket.receive_json() == {
            "kind": "status",
            "mode": "unconfigured",
            "snapshot": None,
        }


def test_stream_sends_tick_frames_and_goes_silent_while_paused(client):
    driver = client.app.state.driver
    assert client.put("/api/scene", json={"robots": [_robot()]}).status_code == 200
    with client.websocket_connect("/ws/state") as websocket:
        first = websocket.receive_json()
        assert first["kind"] == "status"
        assert first["mode"] == "configured"
        assert first["snapshot"]["tick_index"] == 0

        assert client.post("/api/control", json={"action": "start"}).status_code == 200
        ticks = []
        while len(ticks) < 3:
            frame = websocket.receive_json()
            if frame["kind"] == "tick":
                ticks.append(frame["snapshot"]["tick_index"])
        assert ticks == sorted(ticks)
        assert len(set(ticks)) == len(ticks)

        assert client.post("/api/control", json={"action": "pause"}).status_code == 200
        while True:
            frame = websocket.receive_json()
            if frame["kind"] == "status" and frame["mode"] == "paused":
                paused_tick = frame["snapshot"]["tick_index"]
                break
        time.sleep(0.15)
        assert driver.latest_snapshot.tick_index == paused_tick

        assert client.post("/api/control", json={"action": "resume"}).status_code == 200
        frame = websocket.receive_json()
        assert frame["kind"] == "status"
        assert frame["mode"] == "running"
        frame = websocket.receive_json()
        assert frame["kind"] == "tick"
        assert frame["snapshot"]["tick_index"] > paused_tick


def test_websocket_reconnect_reports_current_mode_and_latest_snapshot(client):
    driver = client.app.state.driver
    assert client.put("/api/scene", json={"robots": [_robot()]}).status_code == 200
    assert client.post("/api/control", json={"action": "start"}).status_code == 200
    _wait_until(lambda: driver.latest_snapshot.tick_index >= 3)

    with client.websocket_connect("/ws/state") as websocket:
        first = websocket.receive_json()
        assert first["kind"] == "status"
        assert first["mode"] == "running"
        first_tick = first["snapshot"]["tick_index"]
        assert first_tick >= 3
    _wait_until(lambda: len(driver._subscribers) == 0)

    with client.websocket_connect("/ws/state") as websocket:
        second = websocket.receive_json()
        assert second["kind"] == "status"
        assert second["mode"] == "running"
        assert second["snapshot"]["tick_index"] >= first_tick


def test_tick_frames_match_kernel_snapshots_field_by_field(client):
    body = {"robots": RING_ROBOTS}
    assert client.put("/api/scene", json=body).status_code == 200
    kernel = Simulation.create_scheduled(
        resolve_scene(SceneConfig.model_validate(body)).scenario
    )
    with client.websocket_connect("/ws/state") as websocket:
        websocket.receive_json()
        assert client.post("/api/control", json={"action": "start"}).status_code == 200
        frame = None
        while frame is None:
            candidate = websocket.receive_json()
            if candidate["kind"] == "tick" and candidate["snapshot"]["tick_index"] >= 5:
                frame = candidate

    target_tick = frame["snapshot"]["tick_index"]
    snapshot = None
    for _ in range(target_tick + 1):
        snapshot = kernel.step()
    assert snapshot.tick_index == target_tick
    _assert_snapshot_matches(frame["snapshot"], snapshot)
