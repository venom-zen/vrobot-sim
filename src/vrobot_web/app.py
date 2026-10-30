"""FastAPI application factory and the HTTP / WebSocket interfaces."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Literal, Sequence

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.scenario import ScenarioValidationError
from vrobot_web.driver import SimulationDriver
from vrobot_web.scene import SceneConfig, SceneResolutionError, resolve_scene
from vrobot_web.schemas import MapPayload, SnapshotPayload

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ControlRequest(BaseModel):
    action: Literal["start", "pause", "resume", "reset"]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.driver.shutdown()


def create_app() -> FastAPI:
    """Build the application without binding a socket."""
    app = FastAPI(title="VirtualRobot Live Visualization", lifespan=_lifespan)
    app.state.driver = SimulationDriver()
    _register_http_routes(app)
    _register_websocket_routes(app)
    # The static mount goes last so it never shadows API or WebSocket paths.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def _register_http_routes(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"violations": _violation_texts(exc)})

    @app.get("/api/map", response_model=MapPayload)
    async def read_map() -> MapPayload | JSONResponse:
        try:
            return MapPayload.from_topology(load_map(DEMO_MAP_ID))
        except Exception as exc:  # The built-in map is corrupt; nothing else can render.
            return JSONResponse(status_code=500, content={"violations": [str(exc)]})

    @app.put("/api/scene", response_model=None)
    async def apply_scene(config: SceneConfig) -> dict | JSONResponse:
        driver: SimulationDriver = app.state.driver
        try:
            resolved = resolve_scene(config)
            driver.apply_scene(resolved.scenario)
        except SceneResolutionError as exc:
            return _violations_response(422, exc.violations)
        except ScenarioValidationError as exc:
            return _violations_response(422, exc.violations)
        return {
            "mode": driver.mode,
            "resolved_paths": {
                robot_id: list(path) for robot_id, path in resolved.paths.items()
            },
            "snapshot": SnapshotPayload.from_tick(driver.latest_snapshot),
        }

    @app.post("/api/control", response_model=None)
    async def control(request: ControlRequest) -> dict | JSONResponse:
        driver: SimulationDriver = app.state.driver
        outcome = driver.control(request.action)
        if not outcome.accepted:
            return JSONResponse(
                status_code=409,
                content={"mode": driver.mode, "violations": list(outcome.violations)},
            )
        return {
            "mode": driver.mode,
            "snapshot": SnapshotPayload.from_tick(driver.latest_snapshot),
        }


def _register_websocket_routes(app: FastAPI) -> None:
    @app.websocket("/ws/state")
    async def state_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        driver: SimulationDriver = app.state.driver
        driver.subscribe(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            driver.unsubscribe(websocket)


def _violations_response(status_code: int, violations: Sequence[str]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"violations": list(violations)})


def _violation_texts(exc: RequestValidationError) -> list[str]:
    texts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "invalid value"))
        texts.append(f"{location}: {message}" if location else message)
    return texts or [str(exc)]
