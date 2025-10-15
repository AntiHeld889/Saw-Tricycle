"""Minimal FastAPI application for remote monitoring."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..state import TricycleState

try:  # pragma: no cover - optional dependency
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore
    CORSMiddleware = None  # type: ignore
    uvicorn = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class WebServer:
    def __init__(self) -> None:
        if FastAPI is None:
            raise RuntimeError(
                "FastAPI is not installed; install fastapi[standard] to enable the web UI"
            )
        self._app = FastAPI(title="Saw Tricycle")
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._state: TricycleState | None = None
        self._register_routes()

    def bind_state(self, state: TricycleState) -> None:
        self._state = state

    def _register_routes(self) -> None:
        @self._app.get("/api/state")
        def read_state() -> Dict[str, Any]:
            if not self._state:
                return {"status": "starting"}
            steering = {
                "angle": self._state.steering.angle_deg,
                "target": self._state.steering.target_deg,
            }
            head = {
                "angle": self._state.head.angle_deg,
                "target": self._state.head.target_deg,
            }
            motor = {
                "throttle": self._state.motor.throttle,
                "direction": self._state.motor.direction,
            }
            audio = {
                "track": self._state.audio.current_track,
                "output": self._state.audio.output_id,
            }
            return {
                "status": "ok",
                "steering": steering,
                "head": head,
                "motor": motor,
                "audio": audio,
            }

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        if uvicorn is None:
            raise RuntimeError("uvicorn is required to run the web server")
        LOGGER.info("Starting web server on %s:%s", host, port)
        uvicorn.run(self._app, host=host, port=port)


__all__ = ["WebServer"]
