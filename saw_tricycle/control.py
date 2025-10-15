"""Async orchestration for the Saw Tricycle control stack."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

from evdev import ecodes

from .config import TricycleConfig, load_config
from .gamepad import GamepadListener
from .hardware.audio import AudioManager
from .hardware.motor import MotorDriver
from .hardware.servo import ServoController, ServoDynamics
from .state import TricycleState

LOGGER = logging.getLogger(__name__)


class ControlSystem:
    """High level coordinator that ties together hardware abstractions."""

    def __init__(self, config: Optional[TricycleConfig] = None) -> None:
        self._cfg = config or load_config()
        self._steering_servo = ServoController(
            self._cfg.steering_pwm,
            self._cfg.steering_geometry,
            dynamics=ServoDynamics(rate_deg_s=150.0, smooth_factor=0.2, invert=True),
            initial_angle=self._cfg.steering_geometry.center_deg,
        )
        self._head_servo = ServoController(
            self._cfg.head_pwm,
            self._cfg.head_geometry,
            dynamics=ServoDynamics(rate_deg_s=100.0, smooth_factor=0.1, invert=False),
            initial_angle=self._cfg.head_geometry.center_deg,
        )
        self._motor = MotorDriver(self._cfg.motor)
        self._audio = AudioManager(self._cfg.audio)
        self._gamepad = GamepadListener(self._cfg.gamepad)
        self._state = TricycleState(
            steering=self._steering_servo.state,
            head=self._head_servo.state,
        )
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    @property
    def state(self) -> TricycleState:
        return self._state

    async def start(self) -> None:
        LOGGER.info("Starting control system")
        await self._gamepad.start()
        self._audio.set_output(self._cfg.audio.default_output)
        self._audio.play(self._cfg.audio.start_track)
        self._tasks.append(asyncio.create_task(self._servo_update_loop()))
        self._tasks.append(asyncio.create_task(self._event_loop()))
        self._running = True

    async def stop(self) -> None:
        if not self._running:
            return
        LOGGER.info("Stopping control system")
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        await self._gamepad.stop()
        self._audio.close()
        self._steering_servo.close()
        self._head_servo.close()
        self._motor.close()
        self._running = False

    async def _event_loop(self) -> None:
        async for event_type, code, value in self._gamepad.events():
            if event_type == ecodes.EV_ABS:
                self._handle_abs_event(code, value)
            elif event_type == ecodes.EV_KEY and value == 1:
                self._handle_button_press(code)

    async def _servo_update_loop(self) -> None:
        interval = 0.02
        while True:
            await asyncio.sleep(interval)
            self._steering_servo.update(interval)
            self._head_servo.update(interval)

    def _handle_abs_event(self, code: int, value: int) -> None:
        if code == ecodes.ABS_X:
            self._apply_steering(value)
        elif code == ecodes.ABS_Y:
            self._apply_motor(value)
        elif code == ecodes.ABS_HAT0X:
            self._apply_head(value)

    def _handle_button_press(self, code: int) -> None:
        if code in self._cfg.audio.sound_key_map:
            track = self._cfg.audio.sound_key_map[code]
            self._audio.play(track)
        elif code == ecodes.BTN_START:
            LOGGER.info("Start button pressed; stopping audio")
            self._audio.stop()

    def _apply_steering(self, raw: int) -> None:
        # Normalize to [-1, 1]
        normalized = max(-1.0, min(1.0, raw / 32767.0))
        geo = self._cfg.steering_geometry
        target = geo.center_deg + normalized * (geo.right_max_deg - geo.center_deg)
        if normalized < 0:
            target = geo.center_deg + normalized * (geo.center_deg - geo.left_max_deg)
        LOGGER.debug("Steering target -> %.2f°", target)
        self._steering_servo.set_target(target)

    def _apply_motor(self, raw: int) -> None:
        normalized = max(-1.0, min(1.0, -raw / 32767.0))
        LOGGER.debug("Motor throttle -> %.2f", normalized)
        self._motor.set_output(normalized)

    def _apply_head(self, raw: int) -> None:
        geo = self._cfg.head_geometry
        if raw < 0:
            target = geo.left_deg
        elif raw > 0:
            target = geo.right_deg
        else:
            target = geo.center_deg
        LOGGER.debug("Head target -> %.2f°", target)
        self._head_servo.set_target(target)


async def run_forever() -> None:
    system = ControlSystem()
    await system.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:  # pragma: no cover - manual cancellation
        raise
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt received; shutting down")
    finally:
        await system.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":  # pragma: no cover
    main()
