"""Servo control primitives."""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from ..config import HeadServoGeometry, ServoPWMConfig, SteeringGeometry
from ..state import ServoState

try:  # pragma: no cover - optional dependency on Raspberry Pi
    import pigpio  # type: ignore
except Exception:  # pragma: no cover - allow running in CI without hardware
    pigpio = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass
class ServoDynamics:
    rate_deg_s: float = 180.0
    smooth_factor: float = 0.2
    invert: bool = False


class ServoController:
    """Wrapper around pigpio to drive hobby servos with smoothing."""

    def __init__(
        self,
        pwm: ServoPWMConfig,
        geometry: SteeringGeometry | HeadServoGeometry,
        *,
        dynamics: ServoDynamics = ServoDynamics(),
        initial_angle: Optional[float] = None,
    ) -> None:
        self._pwm = pwm
        self._geometry = geometry
        self._dynamics = dynamics
        self._state = ServoState(
            angle_deg=initial_angle or getattr(geometry, "center_deg", geometry.left_deg),
            target_deg=initial_angle or getattr(geometry, "center_deg", geometry.left_deg),
        )
        self._pigpio = pigpio.pi() if pigpio else None
        if not self._pigpio:
            LOGGER.warning("pigpio is not available; servo commands will be logged only")
        else:
            self._pigpio.set_mode(self._pwm.gpio_pin, pigpio.OUTPUT)

    @property
    def state(self) -> ServoState:
        return self._state

    def close(self) -> None:
        if self._pigpio:
            self._pigpio.set_mode(self._pwm.gpio_pin, pigpio.INPUT)
            self._pigpio.stop()

    def set_target(self, target_deg: float) -> None:
        lower, upper = self._clamp_range()
        clamped = max(lower, min(upper, target_deg))
        self._state.target_deg = clamped

    def update(self, dt: float) -> None:
        target = self._state.target_deg
        current = self._state.angle_deg
        max_delta = self._dynamics.rate_deg_s * dt
        delta = target - current
        if abs(delta) < 1e-4:
            return
        delta = max(-max_delta, min(max_delta, delta))
        new_angle = current + delta * (1.0 - self._dynamics.smooth_factor)
        self._state.angle_deg = new_angle
        self._emit_pulse(new_angle)

    def move_immediate(self, angle_deg: float) -> None:
        self._state.angle_deg = angle_deg
        self._state.target_deg = angle_deg
        self._emit_pulse(angle_deg)

    def _emit_pulse(self, angle_deg: float) -> None:
        pulse = self._angle_to_pulse(angle_deg)
        if self._pigpio:
            self._pigpio.set_servo_pulsewidth(self._pwm.gpio_pin, int(pulse))
        else:
            LOGGER.debug("servo@GPIO%s -> %sµs", self._pwm.gpio_pin, pulse)

    def _angle_to_pulse(self, angle_deg: float) -> float:
        lower, upper = self._clamp_range()
        span = upper - lower
        norm = (angle_deg - lower) / span if span else 0.0
        if self._dynamics.invert:
            norm = 1.0 - norm
        return self._pwm.pulse_min_us + norm * (self._pwm.pulse_max_us - self._pwm.pulse_min_us)

    def _clamp_range(self) -> tuple[float, float]:
        if isinstance(self._geometry, SteeringGeometry):
            return (self._geometry.left_max_deg, self._geometry.right_max_deg)
        return (self._geometry.min_deg, self._geometry.max_deg)

    def __enter__(self) -> "ServoController":
        return self

    def __exit__(self, *exc: object) -> None:
        with suppress(Exception):
            self.close()


__all__ = ["ServoController", "ServoDynamics"]
