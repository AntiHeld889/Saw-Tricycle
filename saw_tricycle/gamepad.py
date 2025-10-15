"""Async helper for receiving events from an evdev compatible gamepad."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import AsyncIterator, Optional

from evdev import InputDevice, ecodes, list_devices

from .config import GamepadConfig

LOGGER = logging.getLogger(__name__)


class GamepadListener:
    def __init__(self, cfg: GamepadConfig) -> None:
        self._cfg = cfg
        self._device: Optional[InputDevice] = None
        self._queue: "asyncio.Queue[tuple[int, int, int]]" = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        await self._connect()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._reader())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._device:
            self._device.close()
        self._task = None
        self._device = None

    async def events(self) -> AsyncIterator[tuple[int, int, int]]:
        while True:
            yield await self._queue.get()

    async def _connect(self) -> None:
        deadline = self._cfg.wait_for_device_s
        while deadline > 0:
            for path in list_devices():
                device = InputDevice(path)
                name = device.name or ""
                if name == self._cfg.name_exact or self._cfg.name_fallback in name:
                    LOGGER.info("Gamepad connected: %s", name)
                    self._device = device
                    device.grab()
                    return
            await asyncio.sleep(1.0)
            deadline -= 1.0
        raise RuntimeError("Gamepad device not found")

    async def _reader(self) -> None:
        assert self._device is not None
        async for event in self._device.async_read_loop():
            if event.type == ecodes.EV_KEY or event.type == ecodes.EV_ABS:
                LOGGER.debug("Gamepad event: %s", event)
                await self._queue.put((event.type, event.code, event.value))


__all__ = ["GamepadListener"]
