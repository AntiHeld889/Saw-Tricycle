"""Cytron MD13S motor driver helper."""

from __future__ import annotations

import logging
from contextlib import suppress

from ..config import MotorDriverConfig
from ..state import MotorState

try:  # pragma: no cover - optional dependency
    import pigpio  # type: ignore
except Exception:  # pragma: no cover
    pigpio = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class MotorDriver:
    def __init__(self, cfg: MotorDriverConfig) -> None:
        self._cfg = cfg
        self._state = MotorState()
        self._pigpio = pigpio.pi() if pigpio else None
        if not self._pigpio:
            LOGGER.warning("pigpio is not available; motor commands will be logged only")
        else:
            self._pigpio.set_mode(cfg.pwm_pin, pigpio.OUTPUT)
            self._pigpio.set_mode(cfg.direction_pin, pigpio.OUTPUT)
            self._pigpio.set_PWM_frequency(cfg.pwm_pin, cfg.pwm_frequency_hz)

    @property
    def state(self) -> MotorState:
        return self._state

    def close(self) -> None:
        if self._pigpio:
            self._pigpio.write(self._cfg.pwm_pin, 0)
            self._pigpio.write(self._cfg.direction_pin, 0)
            self._pigpio.stop()

    def set_output(self, throttle: float) -> None:
        throttle = max(-1.0, min(1.0, throttle))
        direction = 1 if throttle >= 0 else -1
        duty_cycle = abs(throttle)
        self._state.throttle = duty_cycle
        self._state.direction = direction
        if self._pigpio:
            self._pigpio.write(self._cfg.direction_pin, 1 if direction > 0 else 0)
            self._pigpio.set_PWM_dutycycle(self._cfg.pwm_pin, int(duty_cycle * 255))
        else:
            LOGGER.debug(
                "motor@GPIO%s/%s -> dir=%s duty=%.2f",
                self._cfg.pwm_pin,
                self._cfg.direction_pin,
                direction,
                duty_cycle,
            )

    def __enter__(self) -> "MotorDriver":
        return self

    def __exit__(self, *exc: object) -> None:
        with suppress(Exception):
            self.close()


__all__ = ["MotorDriver"]
