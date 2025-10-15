"""Audio output control."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ..config import AudioConfig, AudioRoute
from ..state import AudioState

LOGGER = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, cfg: AudioConfig) -> None:
        self._cfg = cfg
        self._routes: Dict[str, AudioRoute] = {route.id: route for route in cfg.routes}
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._state = AudioState(output_id=cfg.default_output, volume=None)

    @property
    def state(self) -> AudioState:
        return self._state

    def set_output(self, output_id: str) -> None:
        if output_id not in self._routes:
            raise KeyError(f"Unknown audio output: {output_id}")
        route = self._routes[output_id]
        for command in route.setup_commands:
            LOGGER.debug("Running audio setup command: %s", command)
            subprocess.run(command, check=False)
        self._state.output_id = output_id

    def set_volume(self, volume: int) -> None:
        output_id = self._state.output_id
        if output_id is None:
            raise RuntimeError("Audio output not selected")
        route = self._routes.get(output_id)
        if not route or not route.volume_command:
            LOGGER.info("Volume control not available for route %s", output_id)
            return
        volume = max(route.volume_min, min(route.volume_max, volume))
        command = [part.format(volume=volume) for part in route.volume_command]
        LOGGER.debug("Running volume command: %s", command)
        subprocess.run(command, check=False)
        self._state.volume = volume

    def play(self, track: Path) -> None:
        self.stop()
        output_id = self._state.output_id or self._cfg.default_output
        route = self._routes.get(output_id)
        env = None
        if route:
            env = {"ALSA_DEFAULT": route.alsa_device}
        LOGGER.info("Playing track %s on %s", track, output_id)
        self._process = subprocess.Popen(
            ["mpg123", "-q", str(track)],
            env=env,
        )
        self._state.current_track = str(track)

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            LOGGER.debug("Stopping audio playback")
            self._process.terminate()
        self._process = None
        self._state.current_track = None

    def close(self) -> None:
        self.stop()

    def __enter__(self) -> "AudioManager":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["AudioManager"]
