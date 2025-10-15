"""Configuration models for the Saw Tricycle control stack.

The module exposes structured dataclasses that keep the hardware related
constants in one place.  The values mirror the working configuration from the
legacy implementation so that the wiring of the existing tricycle can stay
unchanged while the software stack is redesigned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AudioRoute:
    """Definition of an audio output option that can be selected at runtime."""

    id: str
    label: str
    alsa_device: str
    setup_commands: List[List[str]] = field(default_factory=list)
    volume_command: Optional[List[str]] = None
    volume_min: int = 0
    volume_max: int = 100
    volume_step: int = 1
    volume_default: int = 100


@dataclass(frozen=True)
class ServoPWMConfig:
    """Low level PWM settings shared by the steering and head servos."""

    gpio_pin: int
    pulse_min_us: int
    pulse_max_us: int


@dataclass(frozen=True)
class SteeringGeometry:
    """Calibrated steering angles for the front wheel servo."""

    left_max_deg: float
    center_deg: float
    right_max_deg: float

    @property
    def allowed_range(self) -> tuple[float, float]:
        return (self.left_max_deg, self.right_max_deg)


@dataclass(frozen=True)
class HeadServoGeometry:
    """Calibrated angles for the head servo which is latched to the D-Pad."""

    min_deg: float
    max_deg: float
    left_deg: float
    center_deg: float
    right_deg: float


@dataclass(frozen=True)
class MotorDriverConfig:
    """Pins and constraints for the Cytron MD13S motor driver."""

    pwm_pin: int
    direction_pin: int
    pwm_frequency_hz: int


@dataclass(frozen=True)
class GamepadConfig:
    """Preferred input device names for the gamepad."""

    name_exact: str
    name_fallback: str
    wait_for_device_s: float = 5.0


@dataclass(frozen=True)
class FilesystemConfig:
    """Directories that the application uses to persist state."""

    state_dir: Path = Path("/var/lib/saw-tricycle")

    def resolved(self) -> "FilesystemConfig":
        return FilesystemConfig(state_dir=self.state_dir.expanduser().resolve())


@dataclass(frozen=True)
class AudioConfig:
    start_track: Path
    sound_key_map: Dict[int, Path]
    default_output: str
    routes: List[AudioRoute]


@dataclass(frozen=True)
class TricycleConfig:
    """Aggregate configuration for the entire system."""

    audio: AudioConfig
    steering_pwm: ServoPWMConfig
    steering_geometry: SteeringGeometry
    head_pwm: ServoPWMConfig
    head_geometry: HeadServoGeometry
    motor: MotorDriverConfig
    gamepad: GamepadConfig
    filesystem: FilesystemConfig


def _default_audio_routes() -> List[AudioRoute]:
    return [
        AudioRoute(
            id="headphones",
            label="Kopfhörerbuchse",
            alsa_device="plughw:0,0",
            setup_commands=[["amixer", "-q", "cset", "numid=3", "1"]],
            volume_command=["amixer", "-q", "sset", "Headphone", "{volume}%"],
            volume_default=100,
        ),
        AudioRoute(
            id="usb",
            label="USB-Soundkarte",
            alsa_device="plughw:1,0",
            setup_commands=[],
            volume_command=[
                "amixer",
                "-q",
                "-D",
                "plughw:1,0",
                "sset",
                "PCM",
                "{volume}%",
            ],
            volume_default=100,
        ),
        AudioRoute(
            id="system",
            label="System-Standard",
            alsa_device="default",
            setup_commands=[],
            volume_command=None,
        ),
    ]


_DEFAULT_AUDIO = AudioConfig(
    start_track=Path("/opt/python/sawsounds/Start.mp3"),
    sound_key_map={
        310: Path("/opt/python/sawsounds/Soundtrack.mp3"),
        311: Path("/opt/python/sawsounds/game2.mp3"),
        305: Path("/opt/python/sawsounds/Klingel.mp3"),
        307: Path("/opt/python/sawsounds/Lache.mp3"),
        314: Path("/opt/python/sawsounds/phub.mp3"),
    },
    default_output="headphones",
    routes=_default_audio_routes(),
)


_DEFAULT_CONFIG = TricycleConfig(
    audio=_DEFAULT_AUDIO,
    steering_pwm=ServoPWMConfig(gpio_pin=17, pulse_min_us=600, pulse_max_us=2400),
    steering_geometry=SteeringGeometry(
        left_max_deg=100.0,
        center_deg=150.0,
        right_max_deg=200.0,
    ),
    head_pwm=ServoPWMConfig(gpio_pin=24, pulse_min_us=600, pulse_max_us=2400),
    head_geometry=HeadServoGeometry(
        min_deg=30.0,
        max_deg=150.0,
        left_deg=30.0,
        center_deg=90.0,
        right_deg=150.0,
    ),
    motor=MotorDriverConfig(pwm_pin=18, direction_pin=27, pwm_frequency_hz=20_000),
    gamepad=GamepadConfig(
        name_exact="8BitDo Ultimate C 2.4G Wireless Controller",
        name_fallback="8BitDo",
    ),
    filesystem=FilesystemConfig(),
)


def load_config(overrides: Optional[Dict[str, object]] = None) -> TricycleConfig:
    """Return the default configuration merged with optional overrides.

    The configuration objects are frozen dataclasses to keep them immutable at
    runtime.  We therefore only support returning the baked in defaults for
    now; callers can deep copy and modify the structures if they require
    adjustments.
    """

    if overrides:
        raise NotImplementedError(
            "Runtime overrides are not implemented in the reference build."
        )
    return _DEFAULT_CONFIG


__all__ = [
    "AudioConfig",
    "AudioRoute",
    "FilesystemConfig",
    "GamepadConfig",
    "HeadServoGeometry",
    "MotorDriverConfig",
    "ServoPWMConfig",
    "SteeringGeometry",
    "TricycleConfig",
    "_DEFAULT_CONFIG",
    "load_config",
]
