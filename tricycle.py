#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =========================
#   KONFIGURATION (OBEN)
# =========================

# ---- Audio & Dateien ----
START_MP3_PATH       = "/opt/python/sawsounds/Start.mp3"   # Pfad anpassen falls nötig
ALSA_HP_DEVICE       = "plughw:0,0"           # Analoger Kopfhörer-Ausgang (mit 'aplay -l' prüfen)
ALSA_USB_DEVICE      = "plughw:1,0"           # USB-Soundkarte (mit 'aplay -l' prüfen)
HEADPHONE_VOLUME_DEFAULT = 100
AUDIO_ROUTE_TIMEOUT  = 3                      # Sekunden für amixer-Kommandos

# Vorkonfigurierte Audioausgänge für Web-Dropdown (ID, Label, ALSA-Device, Setup-Kommandos)
HEADPHONE_ROUTE_COMMANDS = [
    ["amixer", "-q", "cset", "numid=3", "1"],             # 0=auto, 1=analog, 2=HDMI (älteres RPi-OS)
]

AUDIO_OUTPUTS = [
    {
        "id": "headphones",
        "label": "Kopfhörerbuchse",
        "alsa_device": ALSA_HP_DEVICE,
        "setup_commands": HEADPHONE_ROUTE_COMMANDS,
        "volume": {
            "min": 0,
            "max": 100,
            "step": 1,
            "default": HEADPHONE_VOLUME_DEFAULT,
            "command": [
                "amixer",
                "-q",
                "sset",
                "Headphone",
                "{volume}%",
            ],
        },
    },
    {
        "id": "usb",
        "label": "USB-Soundkarte",
        "alsa_device": ALSA_USB_DEVICE,
        "setup_commands": [],
        "volume": {
            "min": 0,
            "max": 100,
            "step": 1,
            "default": 100,
            "command": [
                "amixer",
                "-q",
                "-D",
                ALSA_USB_DEVICE,
                "sset",
                "PCM",
                "{volume}%",
            ],
        },
    },
    {
        "id": "system",
        "label": "System-Standard",
        "alsa_device": "default",
        "setup_commands": [],
    },
]

_AUDIO_OUTPUT_MAP = {cfg["id"]: cfg for cfg in AUDIO_OUTPUTS}
DEFAULT_AUDIO_OUTPUT_ID = AUDIO_OUTPUTS[0]["id"] if AUDIO_OUTPUTS else None

# Gleiches File bei erneutem Tastendruck neu starten?
RESTART_SAME_TRACK   = True

# Sound-Tastenbelegung (NUMERISCHE Codes; siehe evdev Events)
SOUND_KEY_MAP = {
    310: "/opt/python/sawsounds/Soundtrack.mp3",  # KEY_310
    311: "/opt/python/sawsounds/game2.mp3",        # KEY_311
    305:  "/opt/python/sawsounds/Klingel.mp3",    # KEY_305
    307:  "/opt/python/sawsounds/Lache.mp3",      # KEY_307
    314:  "/opt/python/sawsounds/phub.mp3",    # KEY_314  (neu)
}

# ---- Reboot-Key ----
REBOOT_KEY_CODE      = 308  # [KEY ] KEY_308 DOWN => sudo reboot

# ---- Gamepad ----
GAMEPAD_NAME_EXACT   = "8BitDo Ultimate C 2.4G Wireless Controller"
GAMEPAD_NAME_FALLBACK= "8BitDo"
WAIT_FOR_DEVICE_S    = 5.0

# ---- Servo 1 (Lenkung auf ABS_Z) ----
GPIO_PIN_SERVO       = 17
US_MIN               = 600
US_MAX               = 2400
SERVO_RANGE_DEG      = 270.0

MID_DEG              = 150.0
LEFT_MAX_DEG         = 100.0
RIGHT_MAX_DEG        = 200.0
STEERING_STEP_DEG    = 0.5

# Standard-Lenkwinkel als Dictionary für Persistenz/Defaults
DEFAULT_STEERING_ANGLES = {
    "left": LEFT_MAX_DEG,
    "mid": MID_DEG,
    "right": RIGHT_MAX_DEG,
}

INVERT_SERVO         = True
DEADZONE_IN          = 0.10
DEADZONE_OUT         = 0.12
EXPO_SERVO           = 0.30
SMOOTH_A_SERVO       = 0.20
RATE_DEG_S           = 150.0
MIN_STEP_DEG         = 0.02
NEUTRAL_HOLD_S       = 2.0
CENTER_SNAP_DEG      = 0.6
NEUTRAL_SNAP_S       = 0.15

# Safe-Start Lenkservo
SERVO_SAFE_START_S   = 0.8
SERVO_ARM_NEUTRAL_MS = 400
SERVO_NEUTRAL_THRESH = 0.08

# Buttons
BTN_CENTER_NAME      = "BTN_SOUTH"  # A
BTN_QUIT_NAME        = "BTN_START"  # Start

# ---- Motor (Cytron MD13S) ----
MOTOR_AXIS_CENTERED_NAME = "ABS_Y"
MOTOR_AXIS_GAS_NAME      = "ABS_GAS"
MOTOR_AXIS_BRAKE_NAME    = "ABS_BRAKE"

GPIO_PIN_MOTOR_PWM   = 18
GPIO_PIN_MOTOR_DIR   = 27
PWM_FREQ_HZ          = 20000
INVERT_MOTOR         = True

DEADZONE_MOTOR       = 0.12
EXPO_MOTOR           = 0.25
SMOOTH_A_MOTOR       = 0.25
RATE_ACCEL_UNITS_S   = 3.0
RATE_DECEL_UNITS_S   = 5.0

MOTOR_LIMIT_FWD      = 0.60
MOTOR_LIMIT_REV      = 0.50
MOTOR_LIMIT_MIN      = 0.0
MOTOR_LIMIT_MAX      = 1.0
MOTOR_LIMIT_STEP     = 0.01
MOTOR_SAFE_START_S   = 1.0
MOTOR_ARM_NEUTRAL_MS = 500
MOTOR_NEUTRAL_THRESH = 0.08
MOTOR_DIR_SWITCH_PAUSE_S = 0.005

# ---- Servo 2 (Kopf per D-Pad, LATCHEND) ----
GPIO_PIN_HEAD        = 24
HEAD_MIN_DEG         = 30.0
HEAD_MAX_DEG         = 150.0
HEAD_LEFT_DEG        = 30.0
HEAD_CENTER_DEG      = 90.0
HEAD_RIGHT_DEG       = 150.0
HEAD_SMOOTH_A        = 0.8
HEAD_RATE_DEG_S      = 100.0
HEAD_SAFE_START_S    = 0.8
HEAD_UPDATE_HYSTERESIS_DEG = 0.2

# ---- Debug/Output ----
PRINT_EVERY_S        = 0.3


# =========================
#   IMPLEMENTIERUNG
# =========================
import math
import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path

try:
    import board  # type: ignore
    import adafruit_ina260  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    board = None  # type: ignore
    adafruit_ina260 = None  # type: ignore

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from evdev import InputDevice, ecodes, list_devices
import pigpio

from webui import load_asset


def _default_state_dir():
    env_path = os.environ.get("SAW_TRICYCLE_STATE_DIR")
    if env_path:
        return Path(env_path)
    return Path.home() / ".config" / "saw-tricycle"


STATE_DIR = _default_state_dir()
AUDIO_SELECTION_FILE = STATE_DIR / "audio-selection.json"


def _load_persisted_state():
    try:
        with AUDIO_SELECTION_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _persist_state(payload):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = AUDIO_SELECTION_FILE.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, AUDIO_SELECTION_FILE)
        return True
    except Exception:
        return False


def _normalize_audio_output_id(audio_id):
    if audio_id is None:
        return None
    audio_id_str = str(audio_id)
    if audio_id_str in _AUDIO_OUTPUT_MAP:
        return audio_id_str
    return None


def _coerce_int(value, fallback):
    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            value = value[:-1]
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return fallback


def _get_volume_profile(audio_id):
    profile = _AUDIO_OUTPUT_MAP.get(str(audio_id))
    if not profile:
        return None
    volume_cfg = profile.get("volume")
    if not isinstance(volume_cfg, dict):
        return None
    command = volume_cfg.get("command")
    if not isinstance(command, (list, tuple)) or not command:
        return None
    command = [str(part) for part in command]

    min_val = _coerce_int(volume_cfg.get("min"), 0)
    max_val = _coerce_int(volume_cfg.get("max"), 100)
    if max_val < min_val:
        min_val, max_val = max_val, min_val
    step_val = _coerce_int(volume_cfg.get("step"), 1)
    if step_val <= 0:
        step_val = 1
    default_val = _coerce_int(volume_cfg.get("default"), max_val)
    default_val = max(min_val, min(max_val, default_val))

    return {
        "command": command,
        "min": min_val,
        "max": max_val,
        "step": step_val,
        "default": default_val,
    }


def _sanitize_volume_value(value, profile):
    try:
        vol = float(value)
    except (TypeError, ValueError):
        return None
    min_val = profile["min"]
    max_val = profile["max"]
    step_val = profile["step"] or 1
    if step_val <= 0:
        step_val = 1
    if vol < min_val:
        vol = min_val
    elif vol > max_val:
        vol = max_val
    base = min_val
    steps = round((vol - base) / step_val)
    vol = base + steps * step_val
    if vol < min_val:
        vol = min_val
    if vol > max_val:
        vol = max_val
    return int(round(vol))


def get_default_volume(audio_id):
    profile = _get_volume_profile(audio_id)
    if not profile:
        return None
    return profile["default"]


def load_persisted_audio_state(default_id=DEFAULT_AUDIO_OUTPUT_ID):
    default_audio = _normalize_audio_output_id(default_id) or DEFAULT_AUDIO_OUTPUT_ID
    state = {
        "audio_device": default_audio,
        "volumes": {},
    }
    data = _load_persisted_state()
    if not data:
        return state

    audio_id = _normalize_audio_output_id(data.get("audio_device"))
    if audio_id:
        state["audio_device"] = audio_id

    volumes = {}
    raw_volumes = data.get("audio_volume") or data.get("audio_volumes") or {}
    if isinstance(raw_volumes, dict):
        for key, raw_value in raw_volumes.items():
            profile = _get_volume_profile(key)
            if not profile:
                continue
            sanitized = _sanitize_volume_value(raw_value, profile)
            if sanitized is None:
                continue
            volumes[str(key)] = sanitized

    selected_profile = _get_volume_profile(state["audio_device"])
    if selected_profile:
        key = state["audio_device"]
        if key in volumes:
            sanitized = _sanitize_volume_value(volumes[key], selected_profile)
            volumes[key] = sanitized if sanitized is not None else selected_profile["default"]
        else:
            volumes[key] = selected_profile["default"]

    state["volumes"] = volumes
    return state


def load_persisted_audio_output(default_id=DEFAULT_AUDIO_OUTPUT_ID):
    return load_persisted_audio_state(default_id).get("audio_device")


def load_persisted_audio_volumes():
    return load_persisted_audio_state().get("volumes", {})


def persist_audio_state(*, audio_device=None, volume_updates=None):
    state = load_persisted_audio_state()
    changed = False

    if audio_device is not None:
        normalized = _normalize_audio_output_id(audio_device)
        if normalized and normalized != state["audio_device"]:
            state["audio_device"] = normalized
            changed = True

    if volume_updates:
        for key, raw_value in volume_updates.items():
            profile = _get_volume_profile(key)
            if not profile:
                continue
            sanitized = _sanitize_volume_value(raw_value, profile)
            if sanitized is None:
                continue
            key_str = str(key)
            if state["volumes"].get(key_str) != sanitized:
                state["volumes"][key_str] = sanitized
                changed = True

    if not changed:
        return False

    payload = _load_persisted_state()
    payload["audio_device"] = state["audio_device"]
    payload["audio_volume"] = state["volumes"]
    return _persist_state(payload)


def persist_audio_output(audio_id):
    return persist_audio_state(audio_device=audio_id)


def persist_audio_volumes(volume_updates):
    return persist_audio_state(volume_updates=volume_updates)


def get_audio_volume_profile(audio_id):
    return _get_volume_profile(audio_id)


def sanitize_audio_volume(audio_id, value):
    profile = _get_volume_profile(audio_id)
    if not profile:
        return None
    return _sanitize_volume_value(value, profile)


def sanitize_motor_limit(value, *, step=MOTOR_LIMIT_STEP):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    numeric = max(MOTOR_LIMIT_MIN, min(MOTOR_LIMIT_MAX, numeric))
    if step and step > 0:
        steps = round((numeric - MOTOR_LIMIT_MIN) / step)
        numeric = MOTOR_LIMIT_MIN + steps * step
    numeric = max(MOTOR_LIMIT_MIN, min(MOTOR_LIMIT_MAX, numeric))
    return round(numeric, 4)


def load_persisted_motor_limits(
    default_forward=MOTOR_LIMIT_FWD, default_reverse=MOTOR_LIMIT_REV
):
    limits = {
        "forward": sanitize_motor_limit(default_forward, step=None)
        or MOTOR_LIMIT_FWD,
        "reverse": sanitize_motor_limit(default_reverse, step=None)
        or MOTOR_LIMIT_REV,
    }
    data = _load_persisted_state()
    raw_limits = data.get("motor_limits") if isinstance(data, dict) else None
    if isinstance(raw_limits, dict):
        forward = sanitize_motor_limit(raw_limits.get("forward"))
        if forward is not None:
            limits["forward"] = forward
        reverse = sanitize_motor_limit(raw_limits.get("reverse"))
        if reverse is not None:
            limits["reverse"] = reverse
    return limits


def persist_motor_limits(*, forward=None, reverse=None):
    current = load_persisted_motor_limits()
    changed = False

    if forward is not None:
        sanitized_forward = sanitize_motor_limit(forward)
        if sanitized_forward is not None and sanitized_forward != current["forward"]:
            current["forward"] = sanitized_forward
            changed = True

    if reverse is not None:
        sanitized_reverse = sanitize_motor_limit(reverse)
        if sanitized_reverse is not None and sanitized_reverse != current["reverse"]:
            current["reverse"] = sanitized_reverse
            changed = True

    if not changed:
        return False

    payload = _load_persisted_state()
    payload["motor_limits"] = {
        "forward": current["forward"],
        "reverse": current["reverse"],
    }
    return _persist_state(payload)


# ---- Lenkungs-Persistenz ----
def _sanitize_steering_value(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    limited = clamp(numeric, 0.0, SERVO_RANGE_DEG)
    if STEERING_STEP_DEG > 0:
        steps = round((limited - 0.0) / STEERING_STEP_DEG)
        limited = 0.0 + steps * STEERING_STEP_DEG
    return round(limited, 3)


def sanitize_steering_angles(payload):
    if not isinstance(payload, dict):
        return None
    left = _sanitize_steering_value(payload.get("left"))
    mid = _sanitize_steering_value(payload.get("mid"))
    right = _sanitize_steering_value(payload.get("right"))
    if left is None or mid is None or right is None:
        return None
    if not (0.0 <= left <= mid <= right <= SERVO_RANGE_DEG):
        return None
    return {"left": left, "mid": mid, "right": right}


def load_persisted_steering_angles(defaults=None):
    if defaults is None:
        defaults = DEFAULT_STEERING_ANGLES
    data = _load_persisted_state()
    if isinstance(data, dict):
        raw = data.get("steering_angles")
        sanitized = sanitize_steering_angles(raw)
        if sanitized:
            return sanitized
    return dict(defaults)


def persist_steering_angles(angles):
    sanitized = sanitize_steering_angles(angles)
    if sanitized is None:
        return False
    payload = _load_persisted_state()
    payload["steering_angles"] = sanitized
    return _persist_state(payload)


def apply_steering_angles(angles):
    sanitized = sanitize_steering_angles(angles)
    if sanitized is None:
        return False
    global LEFT_MAX_DEG, MID_DEG, RIGHT_MAX_DEG
    LEFT_MAX_DEG = sanitized["left"]
    MID_DEG = sanitized["mid"]
    RIGHT_MAX_DEG = sanitized["right"]
    return True


# === Laufzeit-Handle für exklusives MP3-Playback ===
CURRENT_PLAYER_PROC = None
CURRENT_PLAYER_PATH = None


# === Batterieüberwachung ===
class BatteryMonitor:
    """Liest den INA260-Sensor aus und schätzt den Ladezustand eines LiFePO4-Akkus."""

    DEFAULT_SOC_CURVE = [
        (13.6, 100.0),
        (13.4, 95.0),
        (13.3, 90.0),
        (13.2, 80.0),
        (13.1, 70.0),
        (13.0, 60.0),
        (12.9, 50.0),
        (12.8, 40.0),
        (12.7, 30.0),
        (12.6, 20.0),
        (12.4, 10.0),
        (12.2, 5.0),
        (12.0, 0.0),
        (11.8, 0.0),
    ]

    def __init__(self, *, sample_interval=5.0, voltage_soc_curve=None):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sample_interval = max(1.0, float(sample_interval))
        self._curve = (
            list(voltage_soc_curve)
            if voltage_soc_curve is not None
            else list(self.DEFAULT_SOC_CURVE)
        )
        self._curve.sort(key=lambda item: item[0], reverse=True)
        self._state = {
            "status": "unavailable",
            "voltage": None,
            "current": None,
            "power": None,
            "percent": None,
            "charging": False,
            "timestamp": None,
        }
        self._i2c = None
        self._sensor = None
        self._thread = None
        self._error_logged = False

        if board is None or adafruit_ina260 is None:
            print(
                "[BatteryMonitor] Adafruit INA260 Bibliothek nicht verfügbar – Akkuanzeige deaktiviert.",
                file=sys.stderr,
            )
            return

        try:
            self._i2c = board.I2C()  # type: ignore[call-arg]
            self._sensor = adafruit_ina260.INA260(self._i2c)  # type: ignore[call-arg]
            try:
                # Höhere Mittelung sorgt für ein ruhigeres Signal.
                self._sensor.average_count = adafruit_ina260.AveragingCount.COUNT_16  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                self._sensor.mode = adafruit_ina260.Mode.CONTINUOUS  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception as exc:
            print(f"[BatteryMonitor] INA260 konnte nicht initialisiert werden: {exc}", file=sys.stderr)
            self._state["status"] = "error"
            return

        self._state["status"] = "initializing"
        self._thread = threading.Thread(
            target=self._run,
            name="battery-monitor",
            daemon=True,
        )
        self._thread.start()

    def _estimate_percent(self, voltage):
        if voltage is None or not math.isfinite(voltage):
            return None
        if not self._curve:
            return None
        if voltage >= self._curve[0][0]:
            return self._curve[0][1]
        if voltage <= self._curve[-1][0]:
            return self._curve[-1][1]
        for idx in range(len(self._curve) - 1):
            v_hi, p_hi = self._curve[idx]
            v_lo, p_lo = self._curve[idx + 1]
            if v_hi >= voltage >= v_lo:
                span = v_hi - v_lo
                if span <= 0:
                    return p_lo
                ratio = (voltage - v_lo) / span
                return p_lo + ratio * (p_hi - p_lo)
        return None

    def _run(self):
        assert self._sensor is not None
        while not self._stop.is_set():
            try:
                voltage = float(self._sensor.voltage)  # type: ignore[attr-defined]
                current_ma = float(self._sensor.current)  # type: ignore[attr-defined]
                current_a = current_ma / 1000.0
                power_w = None
                try:
                    power_raw = float(self._sensor.power)  # type: ignore[attr-defined]
                except Exception:
                    power_raw = None
                if power_raw is not None and math.isfinite(power_raw):
                    # Laut Datenblatt liefert der INA260 die Leistung in Milliwatt.
                    power_w = power_raw / 1000.0
                percent = self._estimate_percent(voltage)
                percent_clamped = None
                if percent is not None and math.isfinite(percent):
                    percent_clamped = max(0.0, min(100.0, percent))
                charging = current_a <= -0.1
                if charging:
                    status = "charging"
                elif current_a >= 0.1:
                    status = "discharging"
                else:
                    status = "idle"
                snapshot = {
                    "status": status,
                    "voltage": round(voltage, 3),
                    "current": round(current_a, 3),
                    "power": round(power_w, 3) if power_w is not None else None,
                    "percent": round(percent_clamped, 1) if percent_clamped is not None else None,
                    "charging": charging,
                    "timestamp": time.time(),
                }
                with self._lock:
                    self._state = snapshot
                self._error_logged = False
            except Exception as exc:
                if not self._error_logged:
                    print(f"[BatteryMonitor] Messfehler: {exc}", file=sys.stderr)
                    self._error_logged = True
                with self._lock:
                    self._state = {
                        "status": "error",
                        "voltage": None,
                        "current": None,
                        "power": None,
                        "percent": None,
                        "charging": False,
                        "timestamp": time.time(),
                    }
            self._stop.wait(self._sample_interval)

    def get_state(self):
        with self._lock:
            return dict(self._state)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)


# === Websteuerungszustand ===
class WebControlState:
    """Thread-sicherer Zustand für Web-Eingaben."""

    def __init__(
        self,
        *,
        initial_audio_device=None,
        initial_volume_map=None,
        initial_motor_limits=None,
        initial_steering_angles=None,
        battery_monitor=None,
    ):
        self._lock = threading.Lock()
        self._override = False
        self._motor = 0.0
        self._steering = 0.0
        self._head = 0.0
        self._last_update = 0.0
        self._battery_monitor = battery_monitor
        normalized_device = _normalize_audio_output_id(initial_audio_device)
        self._audio_device = normalized_device or DEFAULT_AUDIO_OUTPUT_ID
        self._audio_volumes = {}
        if isinstance(initial_volume_map, dict):
            for key, value in initial_volume_map.items():
                sanitized = sanitize_audio_volume(key, value)
                if sanitized is None:
                    continue
                key_str = str(key)
                self._audio_volumes[key_str] = sanitized
        self._ensure_volume_defaults_locked(self._audio_device)
        self._motor_limit_forward = MOTOR_LIMIT_FWD
        self._motor_limit_reverse = MOTOR_LIMIT_REV
        if isinstance(initial_motor_limits, dict):
            forward = sanitize_motor_limit(initial_motor_limits.get("forward"))
            if forward is not None:
                self._motor_limit_forward = forward
            reverse = sanitize_motor_limit(initial_motor_limits.get("reverse"))
            if reverse is not None:
                self._motor_limit_reverse = reverse
        self._steering_angles = {
            "left": LEFT_MAX_DEG,
            "mid": MID_DEG,
            "right": RIGHT_MAX_DEG,
        }
        if isinstance(initial_steering_angles, dict):
            sanitized = sanitize_steering_angles(initial_steering_angles)
            if sanitized is not None:
                self._steering_angles = sanitized
                apply_steering_angles(sanitized)

    def _ensure_volume_defaults_locked(self, audio_id):
        profile = get_audio_volume_profile(audio_id)
        if not profile:
            return None
        key = str(audio_id)
        current = self._audio_volumes.get(key)
        if current is None:
            current = profile["default"]
        else:
            sanitized = sanitize_audio_volume(key, current)
            if sanitized is None:
                current = profile["default"]
            else:
                current = sanitized
        self._audio_volumes[key] = current
        return current

    def _build_volume_snapshot_locked(self):
        audio_id = self._audio_device
        profile = get_audio_volume_profile(audio_id)
        if not profile:
            return None
        key = str(audio_id)
        value = self._audio_volumes.get(key)
        if value is None:
            value = self._ensure_volume_defaults_locked(audio_id)
        else:
            sanitized = sanitize_audio_volume(audio_id, value)
            if sanitized is None:
                value = self._ensure_volume_defaults_locked(audio_id)
            else:
                if sanitized != value:
                    self._audio_volumes[key] = sanitized
                value = sanitized
        return {
            "value": value,
            "min": profile["min"],
            "max": profile["max"],
            "step": profile["step"],
        }

    def update(
        self,
        *,
        override=None,
        motor=None,
        steering=None,
        head=None,
        audio_device=None,
        audio_volume=None,
        motor_limits=None,
        steering_angles=None,
    ):
        new_audio_id = None
        persist_audio_id = None
        volume_updates = {}
        apply_volume_change = None
        motor_limits_to_persist = None
        steering_angles_to_persist = None
        with self._lock:
            if override is not None:
                self._override = bool(override)
            if motor is not None:
                try:
                    self._motor = clamp(float(motor), -1.0, 1.0)
                except (TypeError, ValueError):
                    pass
            if steering is not None:
                try:
                    self._steering = clamp(float(steering), -1.0, 1.0)
                except (TypeError, ValueError):
                    pass
            if head is not None:
                try:
                    self._head = clamp(float(head), -1.0, 1.0)
                except (TypeError, ValueError):
                    pass
            if audio_device is not None:
                audio_id = str(audio_device)
                if audio_id in _AUDIO_OUTPUT_MAP and audio_id != self._audio_device:
                    self._audio_device = audio_id
                    new_audio_id = audio_id
                    persist_audio_id = audio_id
                    previous_volume = self._audio_volumes.get(audio_id)
                    volume_value = self._ensure_volume_defaults_locked(audio_id)
                    if volume_value is not None:
                        if previous_volume != volume_value:
                            volume_updates[audio_id] = volume_value
                        apply_volume_change = (audio_id, volume_value)
            if audio_volume is not None:
                target_id = self._audio_device
                if target_id:
                    volume_value = sanitize_audio_volume(target_id, audio_volume)
                    if volume_value is not None:
                        current_value = self._audio_volumes.get(target_id)
                        if current_value != volume_value:
                            self._audio_volumes[target_id] = volume_value
                            volume_updates[target_id] = volume_value
                            apply_volume_change = (target_id, volume_value)
            if motor_limits is not None and isinstance(motor_limits, dict):
                changed_limits = False
                forward_value = sanitize_motor_limit(motor_limits.get("forward"))
                if forward_value is not None and forward_value != self._motor_limit_forward:
                    self._motor_limit_forward = forward_value
                    changed_limits = True
                reverse_value = sanitize_motor_limit(motor_limits.get("reverse"))
                if reverse_value is not None and reverse_value != self._motor_limit_reverse:
                    self._motor_limit_reverse = reverse_value
                    changed_limits = True
                if changed_limits:
                    motor_limits_to_persist = {
                        "forward": self._motor_limit_forward,
                        "reverse": self._motor_limit_reverse,
                    }
            if steering_angles is not None and isinstance(steering_angles, dict):
                sanitized = sanitize_steering_angles(steering_angles)
                if sanitized is not None and sanitized != self._steering_angles:
                    self._steering_angles = sanitized
                    steering_angles_to_persist = sanitized
            self._last_update = time.time()
            snapshot = self.snapshot_locked()
        if persist_audio_id is not None:
            persist_audio_output(persist_audio_id)
        if volume_updates:
            persist_audio_volumes(volume_updates)
        if motor_limits_to_persist is not None:
            persist_motor_limits(**motor_limits_to_persist)
        if steering_angles_to_persist is not None:
            apply_steering_angles(steering_angles_to_persist)
            persist_steering_angles(steering_angles_to_persist)
        if new_audio_id is not None:
            apply_audio_output(new_audio_id)
        if apply_volume_change is not None:
            apply_audio_volume(*apply_volume_change)
        return self._finalize_snapshot(snapshot)

    def snapshot(self):
        with self._lock:
            snapshot = self.snapshot_locked()
        return self._finalize_snapshot(snapshot)

    def snapshot_locked(self):
        return {
            "override": self._override,
            "motor": self._motor,
            "steering": self._steering,
            "head": self._head,
            "motor_limits": {
                "forward": self._motor_limit_forward,
                "reverse": self._motor_limit_reverse,
                "min": MOTOR_LIMIT_MIN,
                "max": MOTOR_LIMIT_MAX,
                "step": MOTOR_LIMIT_STEP,
            },
            "steering_angles": {
                "left": self._steering_angles["left"],
                "mid": self._steering_angles["mid"],
                "right": self._steering_angles["right"],
                "min": 0.0,
                "max": SERVO_RANGE_DEG,
                "step": STEERING_STEP_DEG,
            },
            "audio_device": self._audio_device,
            "audio_outputs": [
                {"id": cfg["id"], "label": cfg["label"]}
                for cfg in AUDIO_OUTPUTS
            ],
            "audio_volume": self._build_volume_snapshot_locked(),
            "last_update": self._last_update,
        }

    def _finalize_snapshot(self, snapshot):
        if self._battery_monitor:
            try:
                snapshot["battery"] = self._battery_monitor.get_state()
            except Exception:
                snapshot["battery"] = {"status": "error"}
        return snapshot

    def get_battery_state(self):
        if not self._battery_monitor:
            return None
        try:
            return self._battery_monitor.get_state()
        except Exception:
            return {"status": "error"}

    def get_selected_alsa_device(self):
        with self._lock:
            audio_id = self._audio_device
        profile = get_audio_output(audio_id)
        if profile and profile.get("alsa_device"):
            return profile["alsa_device"]
        return ALSA_HP_DEVICE

    def apply_current_audio_output(self):
        with self._lock:
            audio_id = self._audio_device
            volume_value = self._ensure_volume_defaults_locked(audio_id)
        apply_audio_output(audio_id)
        if volume_value is not None:
            apply_audio_volume(audio_id, volume_value)


class ControlRequestHandler(BaseHTTPRequestHandler):
    """HTTP-Endpunkte für die Websteuerung."""

    control_state = None  # wird beim Start gesetzt

    CONTROL_PAGE_NAME = "control.html"
    SETTINGS_PAGE_NAME = "settings.html"


    BATTERY_PAGE = """<!DOCTYPE html>
<html lang=\"de\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">
  <title>Akku-Details · Saw Tricycle</title>
  <style>
    :root {
      color-scheme: dark;
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
      --safe-left: env(safe-area-inset-left, 0px);
      --safe-right: env(safe-area-inset-right, 0px);
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #0d0d0d;
      color: #f2f2f2;
      margin: 0;
      min-height: 100vh;
      min-height: 100dvh;
      padding: calc(1.4rem + var(--safe-top)) calc(1.4rem + var(--safe-right)) calc(1.4rem + var(--safe-bottom)) calc(1.4rem + var(--safe-left));
      display: flex;
      justify-content: center;
      align-items: center;
      -webkit-text-size-adjust: 100%;
      touch-action: manipulation;
    }
    .card {
      width: 100%;
      max-width: 520px;
      background: rgba(21, 21, 21, 0.95);
      border-radius: 18px;
      padding: clamp(1.4rem, 4vw + 0.6rem, 2rem);
      box-shadow: 0 0 40px rgba(0,0,0,0.45);
      display: flex;
      flex-direction: column;
      gap: 1.2rem;
    }
    .card-header {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .back-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 42px;
      height: 42px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.15);
      background: rgba(255,255,255,0.04);
      color: #f2f2f2;
      cursor: pointer;
      text-decoration: none;
      transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
    }
    .back-button:hover {
      background: rgba(255,255,255,0.08);
      border-color: rgba(255,255,255,0.22);
    }
    .back-button:active {
      transform: scale(0.96);
    }
    .back-button svg {
      width: 22px;
      height: 22px;
      fill: currentColor;
    }
    h1 {
      font-size: clamp(1.4rem, 4vw + 0.2rem, 1.85rem);
      margin: 0;
    }
    .status {
      padding: 0.9rem 1rem;
      border-radius: 12px;
      font-size: 0.95rem;
      line-height: 1.4;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
    }
    .status.status-error {
      background: rgba(255, 59, 48, 0.12);
      border-color: rgba(255, 59, 48, 0.35);
      color: #ff6b60;
    }
    .status.status-success {
      background: rgba(54, 212, 106, 0.12);
      border-color: rgba(54, 212, 106, 0.35);
      color: #73ff9b;
    }
    .status.status-info {
      background: rgba(51, 166, 255, 0.12);
      border-color: rgba(51, 166, 255, 0.35);
      color: #7fc8ff;
    }
    dl {
      margin: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.9rem 1.2rem;
    }
    dt {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgba(242,242,242,0.7);
      margin: 0;
    }
    dd {
      margin: 0.15rem 0 0;
      font-size: 1.35rem;
      font-variant-numeric: tabular-nums;
    }
    .timestamp {
      margin: 0.4rem 0 0;
      font-size: 0.85rem;
      color: rgba(242,242,242,0.7);
    }
    @media (max-width: 480px) {
      dl {
        grid-template-columns: minmax(0, 1fr);
      }
      dd {
        font-size: 1.2rem;
      }
    }
    @media (orientation: landscape) and (max-height: 520px) {
      body {
        padding: calc(0.7rem + var(--safe-top)) calc(0.75rem + var(--safe-right)) calc(0.7rem + var(--safe-bottom)) calc(0.75rem + var(--safe-left));
        align-items: stretch;
      }
      .card {
        padding: 1rem;
        gap: 1rem;
        max-height: calc(100dvh - var(--safe-top) - var(--safe-bottom) - 1.2rem);
        overflow-y: auto;
        overscroll-behavior: contain;
      }
      dl {
        gap: 0.8rem 1rem;
      }
      dd {
        font-size: 1.2rem;
      }
    }
    @media (orientation: landscape) and (max-height: 430px) {
      body {
        padding: calc(0.6rem + var(--safe-top)) calc(0.65rem + var(--safe-right)) calc(0.6rem + var(--safe-bottom)) calc(0.65rem + var(--safe-left));
      }
      .card {
        padding: 0.85rem;
        gap: 0.85rem;
      }
      dl {
        gap: 0.75rem 0.9rem;
      }
    }
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"card-header\">
      <a class=\"back-button\" href=\"/\" aria-label=\"Zurück zur Steuerung\">
        <svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" focusable=\"false\"><path d=\"M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z\"/></svg>
      </a>
      <h1>Akku-Details</h1>
    </div>
    <div id=\"status\" class=\"status status-info\" role=\"status\">Werte werden geladen …</div>
    <dl>
      <div>
        <dt>Status</dt>
        <dd id=\"valueStatus\">–</dd>
      </div>
      <div>
        <dt>Akkuladung</dt>
        <dd id=\"valuePercent\">-- %</dd>
      </div>
      <div>
        <dt>Spannung</dt>
        <dd id=\"valueVoltage\">-- V</dd>
      </div>
      <div>
        <dt>Strom</dt>
        <dd id=\"valueCurrent\">-- A</dd>
      </div>
      <div>
        <dt>Leistung</dt>
        <dd id=\"valuePower\">-- W</dd>
      </div>
      <div>
        <dt>Ladezustand</dt>
        <dd id=\"valueCharging\">–</dd>
      </div>
    </dl>
    <p class=\"timestamp\">Zuletzt aktualisiert: <span id=\"valueTimestamp\">--</span></p>
  </div>
  <script>
    const statusEl = document.getElementById('status');
    const valueStatus = document.getElementById('valueStatus');
    const valuePercent = document.getElementById('valuePercent');
    const valueVoltage = document.getElementById('valueVoltage');
    const valueCurrent = document.getElementById('valueCurrent');
    const valuePower = document.getElementById('valuePower');
    const valueCharging = document.getElementById('valueCharging');
    const valueTimestamp = document.getElementById('valueTimestamp');

    const STATUS_LABELS = {
      charging: 'Lädt',
      discharging: 'Entlädt',
      idle: 'Ruhezustand',
      error: 'Sensorfehler',
      initializing: 'Initialisierung',
      unavailable: 'Nicht verfügbar',
      unknown: 'Unbekannt'
    };

    function setStatus(message, tone = 'info') {
      statusEl.textContent = message;
      statusEl.classList.remove('status-error', 'status-success', 'status-info');
      statusEl.classList.add(`status-${tone}`);
    }

    function formatNumber(value, unit, digits = 2) {
      if (!Number.isFinite(value)) {
        return `--\u00A0${unit}`;
      }
      return `${value.toFixed(digits)}\u00A0${unit}`;
    }

    function formatPercent(value) {
      if (!Number.isFinite(value)) {
        return '--\u00A0%';
      }
      return `${Math.round(Math.max(0, Math.min(100, value)))}\u00A0%`;
    }

    function describeCharging(flag, status) {
      if (typeof flag !== 'boolean') {
        if (status === 'charging') {
          return 'Ja';
        }
        if (status === 'discharging') {
          return 'Nein';
        }
        return '–';
      }
      return flag ? 'Ja' : 'Nein';
    }

    function formatTimestamp(value) {
      if (!Number.isFinite(value) || value <= 0) {
        return '--';
      }
      try {
        const date = new Date(value * 1000);
        return date.toLocaleString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      } catch (err) {
        return '--';
      }
    }

    function updateView(payload) {
      if (!payload || typeof payload !== 'object') {
        valueStatus.textContent = 'Nicht verfügbar';
        valuePercent.textContent = '--\u00A0%';
        valueVoltage.textContent = '--\u00A0V';
        valueCurrent.textContent = '--\u00A0A';
        valuePower.textContent = '--\u00A0W';
        valueCharging.textContent = '–';
        valueTimestamp.textContent = '--';
        setStatus('Akku-Daten sind nicht verfügbar.', 'error');
        return;
      }

      const percent = Number(payload.percent);
      const voltage = Number(payload.voltage);
      const current = Number(payload.current);
      const power = Number(payload.power);
      const status = typeof payload.status === 'string' ? payload.status : 'unknown';
      const chargingFlag = typeof payload.charging === 'boolean' ? payload.charging : null;
      const timestamp = Number(payload.timestamp);

      valueStatus.textContent = STATUS_LABELS[status] ?? STATUS_LABELS.unknown;
      valuePercent.textContent = formatPercent(percent);
      valueVoltage.textContent = formatNumber(voltage, 'V', 2);
      valueCurrent.textContent = formatNumber(current, 'A', 2);
      valuePower.textContent = formatNumber(power, 'W', 2);
      valueCharging.textContent = describeCharging(chargingFlag, status);
      valueTimestamp.textContent = formatTimestamp(timestamp);

      if (status === 'error') {
        setStatus('Sensorfehler – bitte Verkabelung und Stromversorgung prüfen.', 'error');
      } else if (status === 'initializing') {
        setStatus('Sensor initialisiert … bitte warten.', 'info');
      } else if (status === 'unavailable') {
        setStatus('Akku-Daten stehen nicht zur Verfügung.', 'error');
      } else {
        setStatus('Akku-Daten aktualisiert.', 'success');
      }
    }

    async function pollBattery() {
      try {
        const response = await fetch('/api/battery');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        updateView(data);
      } catch (error) {
        console.error('Abfrage der Akku-Daten fehlgeschlagen', error);
        updateView(null);
      }
    }

    pollBattery();
    setInterval(pollBattery, 2000);
  </script>
</body>
</html>"""

    def _write_response(self, status, body, content_type="text/html; charset=utf-8"):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/":
            self._write_response(200, load_asset(self.CONTROL_PAGE_NAME))
            return
        if self.path == "/settings":
            self._write_response(200, load_asset(self.SETTINGS_PAGE_NAME))
            return
        if self.path == "/battery":
            self._write_response(200, self.BATTERY_PAGE)
            return
        if self.path.startswith("/api/state"):
            state = self.control_state.snapshot() if self.control_state else {}
            body = json.dumps(state)
            self._write_response(200, body, "application/json")
            return
        if self.path.startswith("/api/battery"):
            payload = {"status": "unavailable"}
            if self.control_state:
                state = self.control_state.get_battery_state()
                if state:
                    payload = state
            body = json.dumps(payload)
            self._write_response(200, body, "application/json")
            return
        self._write_response(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self.path.startswith("/api/control"):
            self._write_response(404, "Not found", "text/plain; charset=utf-8")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            self._write_response(400, "Ungültiges JSON", "text/plain; charset=utf-8")
            return

        state = {}
        if self.control_state:
            state = self.control_state.update(
                override=data.get("override"),
                motor=data.get("motor"),
                steering=data.get("steering"),
                head=data.get("head"),
                audio_device=data.get("audio_device"),
                audio_volume=data.get("audio_volume"),
                motor_limits=data.get("motor_limits"),
                steering_angles=data.get("steering_angles"),
            )

        body = json.dumps(state)
        self._write_response(200, body, "application/json")

    def log_message(self, format, *args):  # noqa: A003 - Überschreibt BaseHTTPRequestHandler
        # Unterdrückt Standard-Logging, um die Konsole sauber zu halten.
        return


def start_webserver(state):
    """Startet den HTTP-Server für die Websteuerung auf Port 8081."""

    ControlRequestHandler.control_state = state
    server = ThreadingHTTPServer(("0.0.0.0", 8081), ControlRequestHandler)

    thread = threading.Thread(target=server.serve_forever, name="web-control", daemon=True)
    thread.start()
    return server


# --------- Validierung & Hilfsfunktionen ---------
def validate_configuration():
    """Validiert zentrale Konfigurationsparameter beim Programmstart."""

    if not os.path.isabs(START_MP3_PATH):
        raise ValueError("START_MP3_PATH muss ein absoluter Pfad sein")

    if US_MIN >= US_MAX:
        raise ValueError("US_MIN muss kleiner als US_MAX sein")

    if not (0.0 <= LEFT_MAX_DEG <= MID_DEG <= RIGHT_MAX_DEG <= SERVO_RANGE_DEG):
        raise ValueError("Lenkwinkel müssen innerhalb der Servo-Range liegen und sortiert sein")

    if DEADZONE_IN < 0 or DEADZONE_OUT < 0 or DEADZONE_IN >= DEADZONE_OUT:
        raise ValueError("DEADZONE_IN/OUT müssen >=0 und DEADZONE_IN < DEADZONE_OUT sein")

    if not (0.0 <= MOTOR_LIMIT_REV <= 1.0 and 0.0 <= MOTOR_LIMIT_FWD <= 1.0):
        raise ValueError("Motorlimits müssen im Bereich [0, 1] liegen")

    if HEAD_MIN_DEG < 0 or HEAD_MAX_DEG > SERVO_RANGE_DEG or not (HEAD_MIN_DEG <= HEAD_CENTER_DEG <= HEAD_MAX_DEG):
        raise ValueError("Kopf-Servo Winkel sind ungültig")

    if SERVO_ARM_NEUTRAL_MS <= 0 or MOTOR_ARM_NEUTRAL_MS <= 0:
        raise ValueError("ARM_NEUTRAL_MS Werte müssen positiv sein")

    if not AUDIO_OUTPUTS:
        raise ValueError("AUDIO_OUTPUTS darf nicht leer sein")


# --------- Hilfsfunktionen: Mathe/Mapping ---------
def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)

def norm_axis_centered(v, lo, hi):
    """Zentrierte Achse auf [-1..+1]."""
    if hi == lo: return 0.0
    mid  = (hi + lo) / 2.0
    span = (hi - lo) / 2.0
    return (v - mid) / span

def norm_axis_trigger(v, lo, hi):
    """Trigger (GAS/BRAKE) auf [0..1]."""
    if hi == lo: return 0.0
    return clamp((v - lo) / (hi - lo), 0.0, 1.0)

def shape_expo(x, expo=0.3):
    return (1 - expo) * x + (x**3) * expo

def deg_to_us_unclamped(deg):
    d = clamp(deg, 0.0, SERVO_RANGE_DEG)
    return int(US_MIN + (US_MAX - US_MIN) * (d / SERVO_RANGE_DEG))

def deg_to_us_lenkung(deg):
    d = clamp(deg, LEFT_MAX_DEG, RIGHT_MAX_DEG)
    return deg_to_us_unclamped(d)

def axis_to_deg_lenkung(ax):
    if ax >= 0:
        span = RIGHT_MAX_DEG - MID_DEG
        return clamp(MID_DEG + ax * span, LEFT_MAX_DEG, RIGHT_MAX_DEG)
    else:
        span = MID_DEG - LEFT_MAX_DEG
        return clamp(MID_DEG + ax * span, LEFT_MAX_DEG, RIGHT_MAX_DEG)


def axis_to_deg_head(ax):
    ax = clamp(ax, -1.0, +1.0)
    if ax >= 0:
        span = HEAD_RIGHT_DEG - HEAD_CENTER_DEG
        return clamp(HEAD_CENTER_DEG + ax * span, HEAD_MIN_DEG, HEAD_MAX_DEG)
    span = HEAD_CENTER_DEG - HEAD_LEFT_DEG
    return clamp(HEAD_CENTER_DEG + ax * span, HEAD_MIN_DEG, HEAD_MAX_DEG)


# --------- Audio-Helper ---------
def get_audio_output(audio_id):
    if audio_id is None:
        return None
    return _AUDIO_OUTPUT_MAP.get(str(audio_id))


def run_audio_setup(commands):
    for cmd in commands or []:
        try:
            subprocess.run(cmd, check=False, timeout=AUDIO_ROUTE_TIMEOUT)
        except Exception:
            pass


def route_audio_to_headphones():
    """Route Audio → Kopfhörerbuchse & setze Lautstärke."""
    run_audio_setup(HEADPHONE_ROUTE_COMMANDS)


def apply_audio_output(audio_id):
    profile = get_audio_output(audio_id)
    if not profile:
        return False
    run_audio_setup(profile.get("setup_commands", []))
    return True


def apply_audio_volume(audio_id, volume):
    profile = get_audio_volume_profile(audio_id)
    if not profile:
        return False
    sanitized = sanitize_audio_volume(audio_id, volume)
    if sanitized is None:
        return False
    command = [str(part).format(volume=sanitized) for part in profile["command"]]
    try:
        subprocess.run(command, check=False, timeout=AUDIO_ROUTE_TIMEOUT)
        return True
    except Exception:
        return False

def _start_player_async(path, alsa_dev=ALSA_HP_DEVICE):
    """Starte mpg123 bevorzugt, fallback ffplay. Liefert (Popen, playername) oder (None, None)."""
    try_cmds = [
        ["mpg123", "-q", "-a", alsa_dev, path],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", path],
    ]
    for cmd in try_cmds:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return proc, cmd[0]
        except FileNotFoundError:
            continue
        except Exception:
            continue
    print("Kein Player gefunden (mpg123/ffplay). Installiere: sudo apt-get install mpg123 ffmpeg", file=sys.stderr)
    return None, None

def stop_current_sound():
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH
    if CURRENT_PLAYER_PROC is None:
        return
    try:
        CURRENT_PLAYER_PROC.terminate()
        try:
            CURRENT_PLAYER_PROC.wait(timeout=0.4)
        except Exception:
            CURRENT_PLAYER_PROC.kill()
    except Exception:
        pass
    CURRENT_PLAYER_PROC = None
    CURRENT_PLAYER_PATH = None

def play_sound_switch(path, alsa_dev=ALSA_HP_DEVICE, restart_if_same=None):
    """
    Exklusives Abspielen: stoppt laufenden Track und startet 'path'.
    - Wenn 'path' == CURRENT_PLAYER_PATH und RESTART_SAME_TRACK True, wird neu gestartet.
    """
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH

    if restart_if_same is None:
        restart_if_same = RESTART_SAME_TRACK

    # Falls ein alter Player-Prozess schon beendet ist, aufräumen
    try:
        if CURRENT_PLAYER_PROC is not None:
            if CURRENT_PLAYER_PROC.poll() is not None:  # schon exit?
                CURRENT_PLAYER_PROC = None
                CURRENT_PLAYER_PATH = None
    except Exception:
        CURRENT_PLAYER_PROC = None
        CURRENT_PLAYER_PATH = None

    same_file = (CURRENT_PLAYER_PATH is not None) and (
        os.path.abspath(path) == os.path.abspath(CURRENT_PLAYER_PATH)
    )

    if (CURRENT_PLAYER_PROC is not None) and same_file and not restart_if_same:
        return True

    stop_current_sound()
    proc, which = _start_player_async(path, alsa_dev)
    if proc is None:
        return False
    CURRENT_PLAYER_PROC = proc
    CURRENT_PLAYER_PATH = path
    print(f"[MP3] {os.path.basename(path)} (via {which})")
    return True


# --------- evdev / Hardware ---------
def find_gamepad():
    t0 = time.monotonic()
    informed_wait = False
    while True:
        devices = []
        for fn in sorted(list_devices()):
            try:
                devices.append(InputDevice(fn))
            except Exception as e:
                print(f"! Kann {fn} nicht öffnen: {e}")

        chosen = None
        print("Scanne Input-Geräte:")
        for dev in devices:
            try:
                caps = dev.capabilities()
                has_abs = (ecodes.EV_ABS in caps)
                has_key = (ecodes.EV_KEY in caps)
                name = dev.name or ""
                print(f"  - {dev.path:>16}  name='{name}'  EV_ABS={has_abs} EV_KEY={has_key}")
                if has_key and (name == GAMEPAD_NAME_EXACT or GAMEPAD_NAME_FALLBACK in name):
                    chosen = dev
                    if name == GAMEPAD_NAME_EXACT:
                        break
            except Exception as e:
                print(f"    ! Zugriff auf {dev.path} fehlgeschlagen: {e}")

        if chosen:
            print(f"Gefunden: {chosen.path}  name='{chosen.name}'")
            return chosen

        if WAIT_FOR_DEVICE_S <= 0:
            print("Kein passendes Gamepad gefunden!", file=sys.stderr)

        if not informed_wait:
            print(f"Kein Gamepad gefunden – warte bis zu {WAIT_FOR_DEVICE_S:.1f}s …")
            informed_wait = True
        if time.monotonic() - t0 > WAIT_FOR_DEVICE_S:
            print("Timeout: Kein Gamepad gefunden.", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.5)

def get_abs_range(caps, code):
    """Kompatibel für unterschiedliche evdev-Formate."""
    for c, info in caps.get(ecodes.EV_ABS, []):
        if isinstance(c, int) and c == code:
            try:
                return info.min, info.max     # AbsInfo
            except AttributeError:
                return info[1][0], info[1][1] # Tupel-Form
    return None

def read_abs(dev, code):
    try:
        return dev.absinfo(code).value
    except OSError:
        return None


# --------- pigpio / Motor-Pins ---------
def setup_motor_pins(pi):
    pi.set_mode(GPIO_PIN_MOTOR_DIR, pigpio.OUTPUT)
    pi.write(GPIO_PIN_MOTOR_DIR, 0)
    pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, 0)

_last_motor_direction = None


def set_motor(pi, speed_norm):
    global _last_motor_direction

    s = clamp(speed_norm, -1.0, +1.0)
    if abs(s) < 1e-3:
        pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, 0)
        _last_motor_direction = None
        return

    direction = 1 if s > 0 else 0
    if _last_motor_direction is None:
        pi.write(GPIO_PIN_MOTOR_DIR, direction)
    elif direction != _last_motor_direction:
        pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, 0)
        if MOTOR_DIR_SWITCH_PAUSE_S > 0:
            time.sleep(MOTOR_DIR_SWITCH_PAUSE_S)
        pi.write(GPIO_PIN_MOTOR_DIR, direction)

    duty = int(abs(s) * 1_000_000)   # pigpio hardware_PWM erwartet 0..1_000_000
    pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, duty)
    _last_motor_direction = direction


# --------- Main ---------
def main():
    persisted_steering = load_persisted_steering_angles()
    if not apply_steering_angles(persisted_steering):
        apply_steering_angles(DEFAULT_STEERING_ANGLES)
    validate_configuration()

    # Button-/Achskonstanten aus Namen auflösen
    BTN_CENTER = getattr(ecodes, BTN_CENTER_NAME)
    BTN_QUIT   = getattr(ecodes, BTN_QUIT_NAME)

    MOTOR_AXIS_CENTERED = getattr(ecodes, MOTOR_AXIS_CENTERED_NAME)
    MOTOR_AXIS_GAS      = getattr(ecodes, MOTOR_AXIS_GAS_NAME)
    MOTOR_AXIS_BRAKE    = getattr(ecodes, MOTOR_AXIS_BRAKE_NAME)

    # pigpio
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpio läuft nicht. sudo systemctl start pigpiod", file=sys.stderr)
        sys.exit(1)

    setup_motor_pins(pi)
    set_motor(pi, 0.0)
    safe_start_motor_until = time.monotonic() + MOTOR_SAFE_START_S
    safe_start_servo_until = time.monotonic() + SERVO_SAFE_START_S
    safe_start_head_until  = time.monotonic() + HEAD_SAFE_START_S

    # Webserver für Remote-Steuerung
    persisted_audio = load_persisted_audio_state()
    persisted_motor_limits = load_persisted_motor_limits()
    battery_monitor = BatteryMonitor()

    web_state = WebControlState(
        initial_audio_device=persisted_audio.get("audio_device"),
        initial_volume_map=persisted_audio.get("volumes"),
        initial_motor_limits=persisted_motor_limits,
        initial_steering_angles=persisted_steering,
        battery_monitor=battery_monitor,
    )
    web_server = None
    try:
        web_server = start_webserver(web_state)
        print("Websteuerung aktiv: http://<IP>:8081/ (Override schaltet Gamepad aus)")
    except Exception as exc:
        print(f"Webserver konnte nicht gestartet werden: {exc}", file=sys.stderr)
        web_server = None


    # Gamepad
    dev = find_gamepad()

    # Startsound nach erfolgreicher Verbindung
    web_state.apply_current_audio_output()
    play_sound_switch(START_MP3_PATH, web_state.get_selected_alsa_device())

    caps = dev.capabilities()
    if ecodes.EV_ABS not in caps:
        print("Kein EV_ABS – Controller-Modus prüfen!", file=sys.stderr); sys.exit(1)

    # Achsenbereiche
    rng_servo  = get_abs_range(caps, ecodes.ABS_Z)
    rng_center = get_abs_range(caps, MOTOR_AXIS_CENTERED)
    rng_gas    = get_abs_range(caps, MOTOR_AXIS_GAS)
    rng_brake  = get_abs_range(caps, MOTOR_AXIS_BRAKE)

    if rng_servo is None:
        print("Lenkachse (ABS_Z) nicht gefunden!", file=sys.stderr); sys.exit(1)

    lo_s, hi_s = rng_servo
    lo_c, hi_c = (rng_center if rng_center else (0, 0))
    lo_g, hi_g = (rng_gas if rng_gas else (0, 0))
    lo_b, hi_b = (rng_brake if rng_brake else (0, 0))

    have_center = rng_center is not None
    have_gas    = rng_gas    is not None
    have_brake  = rng_brake  is not None

    # Startzustände
    current_deg      = MID_DEG
    target_deg       = MID_DEG
    ax_val_servo     = 0.0
    last_active_ts   = time.monotonic()
    last_zero_ts     = None
    last_print_ts    = 0.0
    last_loop_ts     = time.monotonic()
    in_deadzone_hold = True

    MID_US = deg_to_us_lenkung(MID_DEG)
    pi.set_servo_pulsewidth(GPIO_PIN_SERVO, MID_US)

    motor_speed  = 0.0
    motor_target = 0.0

    motor_armed        = False
    neutral_ok_since_m = None
    steer_armed        = False
    neutral_ok_since_s = None

    head_current     = clamp(HEAD_CENTER_DEG, HEAD_MIN_DEG, HEAD_MAX_DEG)
    head_target      = head_current
    head_filtered    = head_current
    head_motion_start = head_current
    head_motion_end   = head_current
    head_motion_start_ts = time.monotonic()
    head_motion_duration = 0.0
    head_last_sent   = head_current
    pi.set_servo_pulsewidth(GPIO_PIN_HEAD, deg_to_us_unclamped(head_current))

    print("Bereit. A = Zentrieren, Start = Beenden. D-Pad L/R setzt Kopf, D-Pad ↑ zentriert (latchend).")
    print(f"Motorachsen: centered={have_center} GAS={have_gas} BRAKE={have_brake}")
    print(f"Reboot-Key: KEY_{REBOOT_KEY_CODE} (DOWN) startet Systemneustart.")

    try:
        while True:
            now = time.monotonic()
            dt = max(0.001, min(0.05, now - last_loop_ts))
            last_loop_ts = now

            control_snapshot = web_state.snapshot()

            # Events (Buttons & Kopfsteuerung)
            try:
                e = dev.read_one()
                while e:
                    if e.type == ecodes.EV_KEY and e.value == 1:   # nur DOWN
                        if e.code == BTN_CENTER:
                            target_deg = MID_DEG
                            last_zero_ts = now
                        elif e.code == BTN_QUIT:
                            raise KeyboardInterrupt
                        elif e.code in SOUND_KEY_MAP:
                            play_sound_switch(SOUND_KEY_MAP[e.code], web_state.get_selected_alsa_device())
                        elif e.code == REBOOT_KEY_CODE:
                            print("[REBOOT] Stoppe Motor/Servos und starte Neustart …")
                            try:
                                set_motor(pi, 0.0)
                                pi.set_servo_pulsewidth(GPIO_PIN_SERVO, 0)
                                pi.set_servo_pulsewidth(GPIO_PIN_HEAD, 0)
                                stop_current_sound()
                            except Exception:
                                pass
                            try:
                                subprocess.Popen(["sudo", "reboot", "now"])
                            except Exception:
                                try:
                                    subprocess.Popen(["sudo", "/sbin/shutdown", "-r", "now"])
                                except Exception as ex:
                                    print(f"[REBOOT] Fehlgeschlagen: {ex}", file=sys.stderr)
                            raise KeyboardInterrupt

                    elif e.type == ecodes.EV_ABS and now >= safe_start_head_until:
                        # Kopfservo LATCHEND via D-Pad:
                        if e.code == ecodes.ABS_HAT0X:
                            if   e.value == -1: head_target = HEAD_LEFT_DEG
                            elif e.value ==  1: head_target = HEAD_RIGHT_DEG
                        elif e.code == ecodes.ABS_HAT0Y:
                            if e.value == -1: head_target = HEAD_CENTER_DEG

                    e = dev.read_one()
            except OSError:
                pass

            # ===== Lenkservo (ABS_Z) =====
            raw_s = read_abs(dev, ecodes.ABS_Z)
            if raw_s is not None:
                x = norm_axis_centered(raw_s, lo_s, hi_s)
                if INVERT_SERVO: x = -x

                # Arming
                if abs(x) <= SERVO_NEUTRAL_THRESH:
                    if neutral_ok_since_s is None:
                        neutral_ok_since_s = now
                    elif (now - neutral_ok_since_s) * 1000.0 >= SERVO_ARM_NEUTRAL_MS:
                        steer_armed = True
                else:
                    neutral_ok_since_s = None

                # Safe-Start / un-armed
                if (now < safe_start_servo_until) or (not steer_armed):
                    ax_val_servo = 0.0
                    target_deg   = MID_DEG
                else:
                    ax_abs = abs(x)
                    if in_deadzone_hold:
                        if ax_abs >= DEADZONE_OUT:
                            in_deadzone_hold = False
                    else:
                        if ax_abs <= DEADZONE_IN:
                            in_deadzone_hold = True

                    if in_deadzone_hold:
                        shaped = 0.0
                        if last_zero_ts is None:
                            last_zero_ts = now
                    else:
                        shaped = shape_expo(x, EXPO_SERVO)
                        last_zero_ts = None

                    ax_val_servo = clamp(shaped, -1.0, +1.0)
                    target_deg   = axis_to_deg_lenkung(ax_val_servo)
                    if abs(ax_val_servo) > 0.01:
                        last_active_ts = now

            if control_snapshot.get("override"):
                if now >= safe_start_servo_until:
                    steer_armed = True
                ax_val_servo = clamp(control_snapshot.get("steering", 0.0), -1.0, +1.0)
                if INVERT_SERVO:
                    ax_val_servo = -ax_val_servo
                target_deg = axis_to_deg_lenkung(ax_val_servo)
                last_active_ts = now
                last_zero_ts = None
                in_deadzone_hold = False

            # Auto-Zentrierung nach Inaktivität
            if (now - last_active_ts) > NEUTRAL_HOLD_S:
                target_deg = MID_DEG

            # Snap auf Mitte
            if target_deg == MID_DEG:
                if last_zero_ts is not None and (now - last_zero_ts) >= NEUTRAL_SNAP_S:
                    current_deg = MID_DEG
                if abs(current_deg - MID_DEG) <= CENTER_SNAP_DEG:
                    current_deg = MID_DEG

            # Sanftes Nachführen
            filtered_target = current_deg + (target_deg - current_deg) * SMOOTH_A_SERVO
            max_step = RATE_DEG_S * dt
            delta = clamp(filtered_target - current_deg, -max_step, +max_step)
            if 0 < abs(delta) < MIN_STEP_DEG:
                delta = MIN_STEP_DEG if delta > 0 else -MIN_STEP_DEG
            if (current_deg != MID_DEG) or (target_deg != MID_DEG):
                current_deg += delta

            # Puls ausgeben
            pi.set_servo_pulsewidth(GPIO_PIN_SERVO, deg_to_us_lenkung(current_deg if current_deg != MID_DEG else MID_DEG))

            # ===== Motor: kombiniert aus centered + GAS - BRAKE =====
            y_centered = 0.0
            gas        = 0.0
            brake      = 0.0

            if have_center:
                raw_c = read_abs(dev, MOTOR_AXIS_CENTERED)
                if raw_c is not None:
                    y_centered = norm_axis_centered(raw_c, lo_c, hi_c)
                    if INVERT_MOTOR:
                        y_centered = -y_centered

            if have_gas:
                raw_g = read_abs(dev, MOTOR_AXIS_GAS)
                if raw_g is not None:
                    gas = norm_axis_trigger(raw_g, lo_g, hi_g)  # 0..1

            if have_brake:
                raw_b = read_abs(dev, MOTOR_AXIS_BRAKE)
                if raw_b is not None:
                    brake = norm_axis_trigger(raw_b, lo_b, hi_b)  # 0..1

            y_total = clamp(y_centered + gas - brake, -1.0, +1.0)

            if control_snapshot.get("override"):
                if now >= safe_start_motor_until:
                    motor_armed = True
                y_total = clamp(control_snapshot.get("motor", 0.0), -1.0, +1.0)

            # Arming & Deadzone
            if abs(y_total) <= MOTOR_NEUTRAL_THRESH:
                if neutral_ok_since_m is None:
                    neutral_ok_since_m = now
                elif (now - neutral_ok_since_m) * 1000.0 >= MOTOR_ARM_NEUTRAL_MS:
                    motor_armed = True
            else:
                neutral_ok_since_m = None

            if motor_armed:
                if abs(y_total) < DEADZONE_MOTOR:
                    y_shaped = 0.0
                else:
                    sign = 1 if y_total >= 0 else -1
                    y_eff = (abs(y_total) - DEADZONE_MOTOR) / (1 - DEADZONE_MOTOR)
                    y_shaped = shape_expo(sign * y_eff, EXPO_MOTOR)
                motor_target = clamp(y_shaped, -1.0, +1.0)
            else:
                motor_target = 0.0

            # Filter + Safe-Start
            filtered_motor = motor_speed + (motor_target - motor_speed) * SMOOTH_A_MOTOR
            delta_u = filtered_motor - motor_speed
            max_rate = RATE_ACCEL_UNITS_S if delta_u >= 0 else RATE_DECEL_UNITS_S
            max_du = max_rate * dt
            step_u = clamp(delta_u, -max_du, +max_du)
            motor_speed += step_u

            if now < safe_start_motor_until:
                motor_speed = 0.0
                motor_target = 0.0

            # Limits
            limit_forward = MOTOR_LIMIT_FWD
            limit_reverse = MOTOR_LIMIT_REV
            limits_snapshot = control_snapshot.get("motor_limits")
            if isinstance(limits_snapshot, dict):
                forward_limit = sanitize_motor_limit(limits_snapshot.get("forward"))
                if forward_limit is not None:
                    limit_forward = forward_limit
                reverse_limit = sanitize_motor_limit(limits_snapshot.get("reverse"))
                if reverse_limit is not None:
                    limit_reverse = reverse_limit

            if motor_speed > 0:
                motor_speed = min(motor_speed, limit_forward)
            elif motor_speed < 0:
                motor_speed = max(motor_speed, -limit_reverse)

            set_motor(pi, motor_speed)

            if control_snapshot.get("override"):
                if now >= safe_start_head_until:
                    head_override = clamp(control_snapshot.get("head", 0.0), -1.0, +1.0)
                    head_target = axis_to_deg_head(head_override)
                else:
                    head_target = HEAD_CENTER_DEG

            # ===== Kopf-Servo (latchend) =====
            head_target = clamp(head_target, HEAD_MIN_DEG, HEAD_MAX_DEG)
            head_filtered += (head_target - head_filtered) * HEAD_SMOOTH_A

            if abs(head_filtered - head_motion_end) > 1e-4:
                head_motion_start = head_current
                head_motion_end = head_filtered
                head_motion_start_ts = now
                distance = abs(head_motion_end - head_motion_start)
                if HEAD_RATE_DEG_S > 0:
                    head_motion_duration = max(distance / HEAD_RATE_DEG_S, dt)
                else:
                    head_motion_duration = 0.0

            if head_motion_duration <= 0.0 or abs(head_motion_end - head_motion_start) <= 1e-6:
                head_current = head_motion_end
            else:
                progress = clamp((now - head_motion_start_ts) / head_motion_duration, 0.0, 1.0)
                eased = progress * progress * (3.0 - 2.0 * progress)
                head_current = head_motion_start + (head_motion_end - head_motion_start) * eased

                if progress >= 1.0:
                    head_motion_start = head_motion_end
                    head_motion_duration = 0.0

            if abs(head_current - head_last_sent) >= HEAD_UPDATE_HYSTERESIS_DEG:
                pi.set_servo_pulsewidth(GPIO_PIN_HEAD, deg_to_us_unclamped(head_current))
                head_last_sent = head_current

            # Debug-Ausgabe
            if (now - last_print_ts) > PRINT_EVERY_S:
                last_print_ts = now
                armM = "ARMED" if motor_armed else "SAFE"
                armS = "ARMED" if steer_armed else "SAFE"
                print(
                    f"{armS}/{armM} | SERVO x={ax_val_servo:+.3f} tgt={target_deg:6.1f}° pos={current_deg:6.1f}°  |  "
                    f"MOTOR tgt={motor_target:+.3f} out={motor_speed:+.3f}  |  "
                    f"HEAD tgt={head_target:5.1f}° pos={head_current:5.1f}°"
                )

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nBeende – Servo & Motor freigeben …")
    finally:
        try:
            pi.set_servo_pulsewidth(GPIO_PIN_SERVO, 0)
            pi.set_servo_pulsewidth(GPIO_PIN_HEAD, 0)
            set_motor(pi, 0.0)
        except Exception:
            pass
        stop_current_sound()
        pi.stop()
        try:
            web_server.shutdown()
            web_server.server_close()
        except Exception:
            pass
        try:
            battery_monitor.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
