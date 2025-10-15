"""State containers used by the control loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ServoState:
    angle_deg: float
    target_deg: float
    last_update_s: float = 0.0


@dataclass
class MotorState:
    throttle: float = 0.0
    brake: float = 0.0
    direction: int = 0


@dataclass
class AudioState:
    current_track: Optional[str] = None
    output_id: Optional[str] = None
    volume: Optional[int] = None


@dataclass
class TricycleState:
    steering: ServoState
    head: ServoState
    motor: MotorState = field(default_factory=MotorState)
    audio: AudioState = field(default_factory=AudioState)
    overrides: Dict[str, str] = field(default_factory=dict)
