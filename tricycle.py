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
RATE_UNITS_S         = 3.0

MOTOR_LIMIT_FWD      = 0.60
MOTOR_LIMIT_REV      = 0.50
MOTOR_LIMIT_MIN      = 0.0
MOTOR_LIMIT_MAX      = 1.0
MOTOR_LIMIT_STEP     = 0.01
MOTOR_SAFE_START_S   = 1.0
MOTOR_ARM_NEUTRAL_MS = 500
MOTOR_NEUTRAL_THRESH = 0.08

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
    ):
        new_audio_id = None
        persist_audio_id = None
        volume_updates = {}
        apply_volume_change = None
        motor_limits_to_persist = None
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
            self._last_update = time.time()
            snapshot = self.snapshot_locked()
        if persist_audio_id is not None:
            persist_audio_output(persist_audio_id)
        if volume_updates:
            persist_audio_volumes(volume_updates)
        if motor_limits_to_persist is not None:
            persist_motor_limits(**motor_limits_to_persist)
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

    HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Saw Tricycle Websteuerung</title>
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
      gap: 1.2rem;
    }
    .card {
      width: 100%;
      max-width: 860px;
      background: #151515;
      border-radius: 16px;
      padding: clamp(1.2rem, 3vw + 0.4rem, 1.8rem);
      box-shadow: 0 0 40px rgba(0,0,0,0.45);
    }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }
    .card-header h1 {
      margin: 0;
      font-size: clamp(1.25rem, 2.8vw, 1.6rem);
      font-weight: 600;
    }
    .card-actions {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .settings-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: rgba(229,9,20,0.16);
      border: 1px solid rgba(229,9,20,0.3);
      color: #fff;
      text-decoration: none;
      transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
    }
    .settings-button:hover {
      background: rgba(229,9,20,0.28);
      border-color: rgba(229,9,20,0.55);
    }
    .settings-button:active {
      transform: scale(0.96);
    }
    .settings-button svg {
      width: 22px;
      height: 22px;
      fill: currentColor;
    }
    .battery-indicator {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.25rem 0.6rem 0.25rem 0.4rem;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      font-size: 0.82rem;
      line-height: 1;
      color: #f2f2f2;
      transition: background 0.2s ease, border-color 0.2s ease;
      text-decoration: none;
      cursor: pointer;
    }
    .battery-indicator svg {
      width: 34px;
      height: 16px;
    }
    .battery-body {
      fill: none;
      stroke: rgba(255,255,255,0.75);
      stroke-width: 2;
      stroke-linejoin: round;
    }
    .battery-cap {
      fill: rgba(255,255,255,0.75);
    }
    .battery-fill {
      fill: #36d46a;
      transition: fill 0.2s ease, width 0.2s ease;
    }
    .battery-indicator.low .battery-fill {
      fill: #ff3b30;
    }
    .battery-indicator.medium .battery-fill {
      fill: #ffcc00;
    }
    .battery-indicator.charging .battery-fill {
      fill: #33a6ff;
    }
    .battery-indicator.error .battery-fill,
    .battery-indicator.unavailable .battery-fill {
      fill: rgba(242,242,242,0.35);
    }
    .battery-indicator.unavailable {
      opacity: 0.7;
    }
    .battery-indicator span {
      min-width: 2.4rem;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .joystick-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
      margin-top: 1.5rem;
      align-items: start;
    }
    .joystick-card {
      background: rgba(255,255,255,0.04);
      border-radius: 14px;
      padding: 1.2rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .joystick-card h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
    .joystick {
      position: relative;
      border-radius: 18px;
      border: 2px solid rgba(255,255,255,0.08);
      background: radial-gradient(circle at center, rgba(229,9,20,0.28) 0%, rgba(229,9,20,0.08) 60%, rgba(229,9,20,0.0) 100%);
      width: 100%;
      aspect-ratio: 1 / 1;
      min-height: 180px;
      touch-action: none;
      user-select: none;
      transition: border-color 0.2s ease;
    }
    @supports not (aspect-ratio: 1) {
      .joystick { padding-top: 100%; min-height: 0; }
    }
    .joystick::after { content: ""; position: absolute; inset: 16%; border: 1px dashed rgba(255,255,255,0.08); border-radius: 50%; pointer-events: none; }
    .joystick.axis-x::before { content: ""; position: absolute; left: 50%; top: 12%; bottom: 12%; width: 1px; background: rgba(255,255,255,0.12); transform: translateX(-50%); pointer-events: none; }
    .joystick.axis-y::before { content: ""; position: absolute; top: 50%; left: 12%; right: 12%; height: 1px; background: rgba(255,255,255,0.12); transform: translateY(-50%); pointer-events: none; }
    .joystick .knob { position: absolute; top: 50%; left: 50%; width: 38%; height: 38%; border-radius: 50%; background: radial-gradient(circle at 30% 30%, #ff3f4a, #b30009); box-shadow: 0 10px 22px rgba(229,9,20,0.45); transform: translate(-50%, -50%) translate(var(--tx, 0%), var(--ty, 0%)); transition: transform 90ms ease-out; will-change: transform; }
    .joystick.active { border-color: rgba(229,9,20,0.5); }
    .joystick.active .knob { transition: none; }
    .value { font-variant-numeric: tabular-nums; font-size: 0.95rem; color: #bbb; }
    .value strong { color: #fff; }
    label { font-size: 0.95rem; }
    button {
      background: #e50914;
      border: none;
      color: #fff;
      padding: 0.65rem 1.6rem;
      border-radius: 999px;
      font-size: 1rem;
      cursor: pointer;
      transition: background 0.2s ease, transform 0.2s ease;
      touch-action: manipulation;
      min-height: 44px;
      -webkit-tap-highlight-color: transparent;
    }
    button:hover { background: #ff1a25; }
    button:active { transform: translateY(1px); }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .head-controls { display: flex; gap: 0.5rem; }
    .head-controls button { flex: 1; padding: 0.55rem 0.6rem; font-size: 0.9rem; }
    .head-actions { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-top: 0.6rem; }
    .head-actions button { flex: 0 1 auto; }
    .override-toggle { display: inline-flex; align-items: center; gap: 0.4rem; }
    button.ghost { background: rgba(229,9,20,0.16); border: 1px solid rgba(229,9,20,0.32); border-radius: 12px; }
    button.ghost:hover { background: rgba(229,9,20,0.28); }
    button.ghost.active { background: #e50914; border-color: #e50914; box-shadow: 0 0 18px rgba(229,9,20,0.35); }
    input[type="checkbox"] { width: 1.2rem; height: 1.2rem; accent-color: #e50914; }
    .audio-output { display: flex; flex-direction: column; gap: 0.4rem; }
    select {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.12);
      color: #fff;
      padding: 0.55rem 0.75rem;
      border-radius: 12px;
      font-size: 0.95rem;
      min-height: 44px;
    }
    select:focus {
      outline: none;
      border-color: rgba(229,9,20,0.55);
      box-shadow: 0 0 0 2px rgba(229,9,20,0.2);
    }
    footer { margin-top: 2rem; font-size: 0.8rem; color: #666; text-align: center; }
    @media (max-width: 900px) {
      body {
        padding: calc(1.1rem + var(--safe-top)) calc(1.1rem + var(--safe-right)) calc(1.1rem + var(--safe-bottom)) calc(1.1rem + var(--safe-left));
        align-items: stretch;
      }
      .card {
        margin: 0 auto;
        border-radius: 14px;
      }
    }
    @media (max-width: 720px) {
      body {
        padding: calc(0.9rem + var(--safe-top)) calc(0.9rem + var(--safe-right)) calc(1rem + var(--safe-bottom)) calc(0.9rem + var(--safe-left));
      }
      .card {
        border-radius: 12px;
        padding: clamp(1rem, 5vw + 0.3rem, 1.4rem);
      }
      .joystick-grid {
        grid-template-columns: minmax(0, 1fr);
        gap: 1.2rem;
      }
      .joystick {
        min-height: clamp(200px, 60vw, 280px);
      }
      .head-controls button {
        font-size: 1rem;
        padding-block: 0.65rem;
      }
      .head-actions { 
        flex-direction: column;
        align-items: stretch;
      }
      .head-actions button {
        width: 100%;
      }
      .override-toggle {
        justify-content: space-between;
      }
      .audio-output { width: 100%; }
    }
    @media (orientation: landscape) and (max-height: 520px) {
      body { padding: 0.8rem; align-items: flex-start; }
      .card {
        padding: 1.1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        max-height: calc(100vh - 1.6rem);
        overflow-y: auto;
      }
      .joystick-grid {
        margin-top: 0;
        grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr) minmax(0, 1fr);
        gap: 0.9rem;
      }
      .joystick-card { padding: 0.9rem; gap: 0.7rem; }
      .joystick { min-height: 150px; }
      .card footer { margin-top: 0.5rem; }
    }
    @media (orientation: landscape) and (max-height: 430px) {
      body { padding: 0.6rem; }
      .card {
        gap: 0.8rem;
      }
      .joystick-grid {
        grid-template-columns: minmax(0, 1fr) minmax(220px, 0.85fr) minmax(0, 1fr);
        align-items: stretch;
      }
      .joystick-card { min-height: 0; }
      .joystick { min-height: 130px; }
    }
    @media (pointer: coarse) {
      button { font-size: 1.05rem; }
      .head-controls button { font-size: 1.05rem; }
      .value { font-size: 1.05rem; }
      label { font-size: 1.05rem; }
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <h1>Saw Tricycle</h1>
      <div class="card-actions">
        <a id="batteryIndicator" class="battery-indicator unavailable" aria-live="polite" title="Akkustand unbekannt" href="/battery">
          <svg viewBox="0 0 46 24" aria-hidden="true" focusable="false">
            <rect class="battery-body" x="1" y="5" width="36" height="14" rx="3" ry="3" />
            <rect class="battery-cap" x="38" y="9" width="6" height="6" rx="1.5" ry="1.5" />
            <rect id="batteryFill" class="battery-fill" x="3" y="7" width="0" height="10" rx="2" ry="2" />
          </svg>
          <span id="batteryLabel">--%</span>
        </a>
        <a class="settings-button" href="/settings" title="Einstellungen" aria-label="Einstellungen öffnen">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.1 7.1 0 0 0-1.62-.94l-.36-2.54A.5.5 0 0 0 14.92 2h-3.84a.5.5 0 0 0-.5.43l-.36 2.54a7.1 7.1 0 0 0-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L3.69 8.45a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.14.24.43.33.68.22l2.39-.96c.49.39 1.04.71 1.62.94l.36 2.54c.04.25.25.43.5.43h3.84c.25 0 .46-.18.5-.43l.36-2.54c.58-.23 1.13-.55 1.62-.94l2.39.96c.25.11.54.02.68-.22l1.92-3.32a.5.5 0 0 0-.12-.64zm-7.14 2.56a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/>
          </svg>
        </a>
      </div>
    </div>
    <div class="joystick-grid">
      <div class="joystick-card">
        <h2>Motor</h2>
        <div id="motorStick" class="joystick axis-y"><div class="knob"></div></div>
        <div class="value">Motor: <strong><span id="motorVal">+0.00</span></strong></div>
      </div>
      <div class="joystick-card">
        <h2>Kopf</h2>
        <div class="head-controls">
          <button class="ghost" type="button" data-head-value="-1" title="Kopf nach links" aria-label="Kopf nach links">L</button>
          <button class="ghost" type="button" data-head-value="0" title="Kopf zentrieren" aria-label="Kopf zentrieren">Z</button>
          <button class="ghost" type="button" data-head-value="1" title="Kopf nach rechts" aria-label="Kopf nach rechts">R</button>
        </div>
        <div class="head-actions">
          <div class="override-toggle">
            <input id="override" type="checkbox">
            <label for="override">Web-Override aktivieren</label>
          </div>
          <button id="center" type="button">Zentrieren</button>
        </div>
        <div class="value">Kopf: <strong><span id="headVal">+0.00</span></strong></div>
      </div>
      <div class="joystick-card">
        <h2>Lenkung</h2>
        <div id="steeringStick" class="joystick axis-x"><div class="knob"></div></div>
        <div class="value">Lenkung: <strong><span id="steeringVal">+0.00</span></strong></div>
      </div>
    </div>
    <footer>Läuft auf Port 8081 · Ziehen/Tippen zum Steuern</footer>
  </div>
  <script>
    const clampValue = (value) => {
      const num = Number.parseFloat(value);
      if (!Number.isFinite(num)) {
        return 0;
      }
      return Math.max(-1, Math.min(1, num));
    };

    const state = { steering: 0, motor: 0, head: 0, override: false, audioDevice: null, audioVolume: null };
    const steeringVal = document.getElementById('steeringVal');
    const motorVal = document.getElementById('motorVal');
    const headVal = document.getElementById('headVal');
    const headButtons = Array.from(document.querySelectorAll('[data-head-value]'));
    const override = document.getElementById('override');
    const centerBtn = document.getElementById('center');
    const audioSelect = document.getElementById('audioDevice');
    const batteryIndicator = document.getElementById('batteryIndicator');
    const batteryFill = document.getElementById('batteryFill');
    const batteryLabel = document.getElementById('batteryLabel');
    const BATTERY_CLASSES = ['charging', 'low', 'medium', 'error', 'unavailable'];
    const BATTERY_MAX_WIDTH = 32;
    let audioOptionsSignature = '';
    if (audioSelect) {
      audioSelect.disabled = true;
    }

    const formatValue = (value) => {
      const rounded = clampValue(value);
      return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(2)}`;
    };

    const updateBattery = (info) => {
      if (!batteryIndicator || !batteryFill || !batteryLabel) {
        return;
      }
      batteryIndicator.classList.remove(...BATTERY_CLASSES);
      if (!info || typeof info !== 'object') {
        batteryLabel.textContent = '--%';
        batteryFill.setAttribute('width', '0');
        batteryIndicator.classList.add('unavailable');
        batteryIndicator.title = 'Akkustand nicht verfügbar';
        return;
      }
      const percentRaw = Number(info.percent);
      const percent = Number.isFinite(percentRaw) ? Math.max(0, Math.min(100, percentRaw)) : null;
      const voltageRaw = Number(info.voltage);
      const voltage = Number.isFinite(voltageRaw) ? voltageRaw : null;
      const currentRaw = Number(info.current);
      const current = Number.isFinite(currentRaw) ? currentRaw : null;
      const powerRaw = Number(info.power);
      const power = Number.isFinite(powerRaw) ? powerRaw : null;
      const status = typeof info.status === 'string' ? info.status : 'unknown';

      if (percent === null) {
        batteryLabel.textContent = '--%';
        batteryFill.setAttribute('width', '0');
      } else {
        batteryLabel.textContent = `${Math.round(percent)}%`;
        const width = (BATTERY_MAX_WIDTH * percent) / 100;
        batteryFill.setAttribute('width', width > 0 ? width.toFixed(1) : '0');
      }

      let indicatorClass = null;
      if (status === 'error') {
        indicatorClass = 'error';
      } else if (status === 'charging') {
        indicatorClass = 'charging';
      } else if (status === 'initializing') {
        indicatorClass = 'unavailable';
      } else if (percent === null) {
        indicatorClass = 'unavailable';
      } else if (percent <= 20) {
        indicatorClass = 'low';
      } else if (percent <= 50) {
        indicatorClass = 'medium';
      }
      if (indicatorClass) {
        batteryIndicator.classList.add(indicatorClass);
      }

      const parts = [];
      if (percent === null) {
        parts.push('Akkuladung unbekannt');
      } else {
        parts.push(`Akkuladung ${Math.round(percent)}%`);
      }
      if (voltage !== null) {
        parts.push(`${voltage.toFixed(2)} V`);
      }
      if (current !== null) {
        const sign = current >= 0 ? '+' : '';
        parts.push(`${sign}${current.toFixed(2)} A`);
      }
      if (power !== null) {
        const sign = power >= 0 ? '+' : '';
        parts.push(`${sign}${power.toFixed(2)} W`);
      }
      if (status === 'charging') {
        parts.push('lädt');
      } else if (status === 'discharging') {
        parts.push('entlädt');
      } else if (status === 'idle') {
        parts.push('Ruhezustand');
      } else if (status === 'error') {
        parts.push('Sensorfehler');
      } else if (status === 'initializing') {
        parts.push('Initialisierung läuft');
      } else if (status === 'unknown') {
        parts.push('Status unbekannt');
      }
      batteryIndicator.title = parts.join(' · ');
    };

    const updateLabels = () => {
      steeringVal.textContent = formatValue(state.steering);
      motorVal.textContent = formatValue(state.motor);
      headVal.textContent = formatValue(state.head);
    };

    const updateHeadButtons = () => {
      headButtons.forEach((button) => {
        const raw = button.dataset.headValue;
        const value = Number.parseFloat(raw ?? '0');
        if (!Number.isFinite(value)) {
          return;
        }
        button.classList.toggle('active', Math.abs(state.head - value) < 0.01);
      });
    };

    const syncAudioSelection = (options, selectedId) => {
      if (!audioSelect) {
        return;
      }
      const normalized = Array.isArray(options)
        ? options
            .map((opt) => ({ id: opt?.id ?? '', label: opt?.label ?? String(opt?.id ?? '') }))
            .filter((opt) => String(opt.id).length > 0)
        : [];
      const signature = JSON.stringify(normalized);
      if (signature !== audioOptionsSignature) {
        audioOptionsSignature = signature;
        audioSelect.innerHTML = '';
        normalized.forEach((opt) => {
          const option = document.createElement('option');
          option.value = String(opt.id);
          option.textContent = opt.label;
          audioSelect.append(option);
        });
      }
      const desired = String(selectedId ?? '');
      const hasDesired = normalized.some((opt) => String(opt.id) === desired);
      const fallback = normalized.length > 0 ? String(normalized[0].id) : '';
      const targetValue = hasDesired ? desired : fallback;
      if (audioSelect.value !== targetValue) {
        audioSelect.value = targetValue;
      }
      audioSelect.disabled = normalized.length === 0;
      state.audioDevice = targetValue || null;
    };

    const setHead = (value, emit = true) => {
      state.head = clampValue(value);
      updateLabels();
      updateHeadButtons();
      if (emit) {
        sendState();
      }
    };

    function createJoystick(id, axis, onInput) {
      const pad = document.getElementById(id);
      let pointerId = null;
      let active = false;
      let value = 0;
      const travel = 42; // Prozentuale Auslenkung für den Knopf

      const render = () => {
        if (axis === 'x') {
          pad.style.setProperty('--tx', `${value * travel}%`);
          pad.style.setProperty('--ty', '0%');
        } else {
          pad.style.setProperty('--ty', `${value * -travel}%`);
          pad.style.setProperty('--tx', '0%');
        }
      };

      const applyValue = (next, emit) => {
        value = clampValue(next);
        render();
        if (emit && typeof onInput === 'function') {
          onInput(value);
        }
      };

      const updateFromPointer = (event) => {
        const rect = pad.getBoundingClientRect();
        let next = 0;
        if (axis === 'x') {
          const centerX = rect.left + rect.width / 2;
          next = (event.clientX - centerX) / (rect.width / 2);
        } else {
          const centerY = rect.top + rect.height / 2;
          next = (centerY - event.clientY) / (rect.height / 2);
        }
        applyValue(next, true);
      };

      const releasePointer = (event) => {
        if (event.pointerId !== pointerId) {
          return;
        }
        try {
          pad.releasePointerCapture(pointerId);
        } catch (err) {
          /* ignore */
        }
        pointerId = null;
        active = false;
        pad.classList.remove('active');
        applyValue(0, true);
      };

      pad.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        pointerId = event.pointerId;
        active = true;
        pad.classList.add('active');
        try {
          pad.setPointerCapture(pointerId);
        } catch (err) {
          /* ignore */
        }
        updateFromPointer(event);
      });

      pad.addEventListener('pointermove', (event) => {
        if (!active || event.pointerId !== pointerId) {
          return;
        }
        updateFromPointer(event);
      });

      pad.addEventListener('pointerup', releasePointer);
      pad.addEventListener('pointercancel', releasePointer);
      pad.addEventListener('contextmenu', (event) => {
        event.preventDefault();
      });

      return {
        setValue(next) {
          applyValue(next, false);
        },
        reset() {
          applyValue(0, false);
        },
        get value() {
          return value;
        },
        get active() {
          return active;
        }
      };
    }

    async function sendState(overrides = {}) {
      const payload = {
        steering: clampValue(overrides.steering ?? state.steering),
        motor: clampValue(overrides.motor ?? state.motor),
        head: clampValue(overrides.head ?? state.head),
        override: overrides.override ?? state.override
      };
      state.steering = payload.steering;
      state.motor = payload.motor;
      state.head = payload.head;
      state.override = payload.override;
      const audioDevice = overrides.audioDevice ?? state.audioDevice;
      if (typeof audioDevice === 'string' && audioDevice.length > 0) {
        payload.audio_device = audioDevice;
        state.audioDevice = audioDevice;
      }
      const audioVolume = overrides.audioVolume ?? state.audioVolume;
      if (Number.isFinite(audioVolume)) {
        const normalized = Math.max(0, Math.min(100, audioVolume));
        payload.audio_volume = Math.round(normalized);
        state.audioVolume = normalized;
      }
      try {
        await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } catch (err) {
        console.error('Senden fehlgeschlagen', err);
      }
    }

    const steeringStick = createJoystick('steeringStick', 'x', (value) => {
      state.steering = value;
      updateLabels();
      sendState();
    });

    const motorStick = createJoystick('motorStick', 'y', (value) => {
      state.motor = value;
      updateLabels();
      sendState();
    });

    headButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const raw = button.dataset.headValue;
        const value = Number.parseFloat(raw ?? '0');
        if (!Number.isFinite(value)) {
          return;
        }
        setHead(value);
      });
    });

    override.addEventListener('change', () => {
      state.override = override.checked;
      sendState();
    });

    centerBtn.addEventListener('click', () => {
      state.steering = 0;
      state.motor = 0;
      steeringStick.reset();
      motorStick.reset();
      setHead(0, false);
      sendState({ steering: 0, motor: 0, head: 0 });
    });

    if (audioSelect) {
      audioSelect.addEventListener('change', () => {
        const value = audioSelect.value;
        state.audioDevice = value || null;
        if (state.audioDevice) {
          sendState({ audioDevice: state.audioDevice });
        }
      });
    }

    async function pollState() {
      try {
        const resp = await fetch('/api/state');
        if (!resp.ok) {
          return;
        }
        const data = await resp.json();
        const remoteSteering = clampValue(data.steering ?? 0);
        const remoteMotor = clampValue(data.motor ?? 0);
        const remoteHead = clampValue(data.head ?? 0);
        const remoteOverride = Boolean(data.override);
        const remoteAudioDevice = typeof data.audio_device === 'string' ? data.audio_device : null;
        const remoteAudioOutputs = Array.isArray(data.audio_outputs) ? data.audio_outputs : [];

        if (!steeringStick.active) {
          state.steering = remoteSteering;
          steeringStick.setValue(remoteSteering);
        }
        if (!motorStick.active) {
          state.motor = remoteMotor;
          motorStick.setValue(remoteMotor);
        }
        state.head = remoteHead;
        state.override = remoteOverride;
        override.checked = remoteOverride;
        updateHeadButtons();
        updateLabels();
        syncAudioSelection(remoteAudioOutputs, remoteAudioDevice);
        if (data.audio_volume && Number.isFinite(data.audio_volume.value)) {
          state.audioVolume = data.audio_volume.value;
        } else {
          state.audioVolume = null;
        }
        updateBattery(data.battery ?? null);
      } catch (err) {
        console.error('Poll fehlgeschlagen', err);
      }
    }

    updateLabels();
    updateHeadButtons();
    updateBattery(null);
    pollState();
    setInterval(pollState, 1500);
  </script>
</body>
</html>"""

    SETTINGS_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Einstellungen · Saw Tricycle</title>
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
    .settings-card {
      width: 100%;
      max-width: 520px;
      background: #151515;
      border-radius: 16px;
      padding: clamp(1.2rem, 4vw + 0.4rem, 1.8rem);
      box-shadow: 0 0 40px rgba(0,0,0,0.45);
      display: flex;
      flex-direction: column;
      gap: 1.4rem;
    }
    .settings-header {
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
      border-radius: 12px;
      background: rgba(229,9,20,0.16);
      border: 1px solid rgba(229,9,20,0.3);
      color: #fff;
      text-decoration: none;
      transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
    }
    .back-button:hover {
      background: rgba(229,9,20,0.28);
      border-color: rgba(229,9,20,0.55);
    }
    .back-button:active {
      transform: translateY(1px);
    }
    .settings-header h1 {
      margin: 0;
      font-size: clamp(1.25rem, 3vw, 1.7rem);
      font-weight: 600;
    }
    .settings-section {
      background: rgba(255,255,255,0.04);
      border-radius: 14px;
      padding: 1.2rem;
      display: flex;
      flex-direction: column;
      gap: 0.9rem;
    }
    .settings-section h2 {
      margin: 0;
      font-size: 1.1rem;
      font-weight: 600;
    }
    label { font-size: 0.95rem; }
    select {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.12);
      color: #fff;
      padding: 0.55rem 0.75rem;
      border-radius: 12px;
      font-size: 0.95rem;
      min-height: 44px;
    }
    select:focus {
      outline: none;
      border-color: rgba(229,9,20,0.55);
      box-shadow: 0 0 0 3px rgba(229,9,20,0.2);
    }
    .audio-volume {
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }
    .motor-limits {
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }
    .slider-row {
      display: flex;
      align-items: center;
      gap: 0.9rem;
    }
    input[type="range"] {
      width: 100%;
      accent-color: #e50914;
    }
    output {
      min-width: 3ch;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .settings-section p.hint {
      margin: 0;
      color: #bbb;
      font-size: 0.9rem;
    }
    .status {
      font-size: 0.95rem;
      color: #bbb;
      min-height: 1.2em;
    }
    .status.success { color: #63f58c; }
    .status.error { color: #ff7a7a; }
    @media (max-width: 640px) {
      body {
        padding: calc(1rem + var(--safe-top)) calc(1rem + var(--safe-right)) calc(1rem + var(--safe-bottom)) calc(1rem + var(--safe-left));
      }
      .settings-card {
        border-radius: 12px;
      }
    }
  </style>
</head>
<body>
  <div class="settings-card">
    <div class="settings-header">
      <a class="back-button" href="/" aria-label="Zurück zur Steuerung" title="Zurück">⟵</a>
      <h1>Einstellungen</h1>
    </div>
    <section class="settings-section">
      <h2>Audio-Ausgabe</h2>
      <div class="audio-output">
        <label for="audioDevice">Ausgabegerät auswählen</label>
        <select id="audioDevice" aria-label="Audio-Ausgabe auswählen"></select>
      </div>
      <div class="audio-volume" id="audioVolumeContainer" hidden>
        <label for="audioVolume">Lautstärke</label>
        <div class="slider-row">
          <input id="audioVolume" type="range" min="0" max="100" step="1" aria-label="Lautstärke einstellen">
          <output id="audioVolumeValue" for="audioVolume">0%</output>
        </div>
      </div>
      <p id="status" class="status"></p>
    </section>
    <section class="settings-section">
      <h2>Motorgrenzen</h2>
      <p class="hint">Begrenzt den maximalen PWM-Anteil für den DC-Motor (0–100&nbsp;%).</p>
      <div class="motor-limits">
        <label for="motorForward">Vorwärts</label>
        <div class="slider-row">
          <input id="motorForward" type="range" min="0" max="100" step="1" aria-label="Vorwärtslimit einstellen">
          <output id="motorForwardValue" for="motorForward">–</output>
        </div>
      </div>
      <div class="motor-limits">
        <label for="motorReverse">Rückwärts</label>
        <div class="slider-row">
          <input id="motorReverse" type="range" min="0" max="100" step="1" aria-label="Rückwärtslimit einstellen">
          <output id="motorReverseValue" for="motorReverse">–</output>
        </div>
      </div>
    </section>
  </div>
  <script>
    const audioSelect = document.getElementById('audioDevice');
    const statusEl = document.getElementById('status');
    const volumeContainer = document.getElementById('audioVolumeContainer');
    const volumeSlider = document.getElementById('audioVolume');
    const volumeValue = document.getElementById('audioVolumeValue');
    const motorForward = document.getElementById('motorForward');
    const motorReverse = document.getElementById('motorReverse');
    const motorForwardValue = document.getElementById('motorForwardValue');
    const motorReverseValue = document.getElementById('motorReverseValue');
    audioSelect.disabled = true;
    let audioOptionsSignature = '';
    let volumeConfig = null;
    let motorConfig = null;
    if (volumeSlider) {
      volumeSlider.disabled = true;
    }
    if (volumeContainer) {
      volumeContainer.hidden = true;
    }
    if (motorForward) {
      motorForward.disabled = true;
      motorForward.value = '0';
    }
    if (motorReverse) {
      motorReverse.disabled = true;
      motorReverse.value = '0';
    }
    if (motorForwardValue) {
      motorForwardValue.textContent = '–';
    }
    if (motorReverseValue) {
      motorReverseValue.textContent = '–';
    }

    const setStatus = (message, tone = '') => {
      statusEl.textContent = message ?? '';
      statusEl.classList.remove('success', 'error');
      if (tone === 'success') {
        statusEl.classList.add('success');
      } else if (tone === 'error') {
        statusEl.classList.add('error');
      }
    };

    const formatMotorPercent = (value) => `${Math.round((Number.parseFloat(value) || 0) * 100)}%`;

    const clampMotorLimit = (value) => {
      if (!motorConfig) {
        return null;
      }
      const { min, max, step } = motorConfig;
      const numeric = Number.parseFloat(value);
      if (!Number.isFinite(numeric)) {
        return null;
      }
      const limited = Math.max(min, Math.min(max, numeric));
      const steps = Math.round((limited - min) / step);
      const quantized = min + steps * step;
      const clamped = Math.max(min, Math.min(max, quantized));
      return Number.parseFloat(clamped.toFixed(4));
    };

    const clampMotorFromSlider = (value) => {
      if (!motorConfig) {
        return null;
      }
      const numeric = Number.parseFloat(value);
      if (!Number.isFinite(numeric)) {
        return null;
      }
      return clampMotorLimit(numeric / 100);
    };

    const syncMotorLimits = (info) => {
      if (!motorForward || !motorReverse || !motorForwardValue || !motorReverseValue) {
        return null;
      }
      if (!info || !Number.isFinite(info.forward) || !Number.isFinite(info.reverse)) {
        motorConfig = null;
        motorForward.disabled = true;
        motorReverse.disabled = true;
        motorForwardValue.textContent = '–';
        motorReverseValue.textContent = '–';
        return null;
      }
      const min = Number.isFinite(info.min) ? info.min : 0;
      const max = Number.isFinite(info.max) ? info.max : 1;
      const step = Number.isFinite(info.step) && info.step > 0 ? info.step : 0.01;
      motorConfig = { min, max, step };
      const sliderMin = Math.round(min * 100);
      const sliderMax = Math.round(max * 100);
      const sliderStep = Math.max(1, Math.round(step * 100));
      motorForward.min = String(sliderMin);
      motorForward.max = String(sliderMax);
      motorForward.step = String(sliderStep);
      motorReverse.min = String(sliderMin);
      motorReverse.max = String(sliderMax);
      motorReverse.step = String(sliderStep);
      const forwardValue = clampMotorLimit(info.forward);
      const reverseValue = clampMotorLimit(info.reverse);
      if (forwardValue === null || reverseValue === null) {
        motorConfig = null;
        motorForward.disabled = true;
        motorReverse.disabled = true;
        motorForwardValue.textContent = '–';
        motorReverseValue.textContent = '–';
        return null;
      }
      motorForward.disabled = false;
      motorReverse.disabled = false;
      motorForward.value = String(Math.round(forwardValue * 100));
      motorReverse.value = String(Math.round(reverseValue * 100));
      motorForwardValue.textContent = formatMotorPercent(forwardValue);
      motorReverseValue.textContent = formatMotorPercent(reverseValue);
      return { forward: forwardValue, reverse: reverseValue };
    };

    const getCurrentMotorValues = () => {
      if (!motorConfig || !motorForward || !motorReverse) {
        return null;
      }
      const forward = clampMotorFromSlider(motorForward.value);
      const reverse = clampMotorFromSlider(motorReverse.value);
      if (forward === null || reverse === null) {
        return null;
      }
      return { forward, reverse };
    };

    const syncAudioSelection = (options, selectedId) => {
      const normalized = Array.isArray(options)
        ? options
            .map((opt) => ({ id: opt?.id ?? '', label: opt?.label ?? String(opt?.id ?? '') }))
            .filter((opt) => String(opt.id).length > 0)
        : [];
      const signature = JSON.stringify(normalized);
      if (signature !== audioOptionsSignature) {
        audioOptionsSignature = signature;
        audioSelect.innerHTML = '';
        normalized.forEach((opt) => {
          const option = document.createElement('option');
          option.value = String(opt.id);
          option.textContent = opt.label;
          audioSelect.append(option);
        });
      }
      const desired = String(selectedId ?? '');
      const hasDesired = normalized.some((opt) => String(opt.id) === desired);
      const fallback = normalized.length > 0 ? String(normalized[0].id) : '';
      const targetValue = hasDesired ? desired : fallback;
      if (audioSelect.value !== targetValue) {
        audioSelect.value = targetValue;
      }
      audioSelect.disabled = normalized.length === 0;
      return targetValue || null;
    };

    const formatVolume = (value) => `${Math.round(Number.parseFloat(value) || 0)}%`;

    const clampVolume = (raw) => {
      if (!volumeConfig) {
        return null;
      }
      const { min, max, step } = volumeConfig;
      const numeric = Number.parseFloat(raw);
      if (!Number.isFinite(numeric)) {
        return null;
      }
      const limited = Math.max(min, Math.min(max, numeric));
      const steps = Math.round((limited - min) / step);
      return min + steps * step;
    };

    const syncVolume = (info) => {
      if (!volumeSlider || !volumeValue || !volumeContainer) {
        return null;
      }
      if (!info || !Number.isFinite(info.value)) {
        volumeConfig = null;
        volumeContainer.hidden = true;
        volumeSlider.disabled = true;
        volumeValue.textContent = '–';
        return null;
      }
      const min = Number.isFinite(info.min) ? info.min : 0;
      const max = Number.isFinite(info.max) ? info.max : 100;
      const step = Number.isFinite(info.step) && info.step > 0 ? info.step : 1;
      volumeConfig = { min, max, step };
      volumeSlider.min = String(min);
      volumeSlider.max = String(max);
      volumeSlider.step = String(step);
      const value = clampVolume(info.value);
      if (value === null) {
        volumeConfig = null;
        volumeContainer.hidden = true;
        volumeSlider.disabled = true;
        volumeValue.textContent = '–';
        return null;
      }
      volumeSlider.value = String(value);
      volumeSlider.disabled = false;
      volumeContainer.hidden = false;
      volumeValue.textContent = formatVolume(value);
      return value;
    };

    async function loadState() {
      try {
        setStatus('Lade aktuelle Einstellungen …');
        const resp = await fetch('/api/state');
        if (!resp.ok) {
          throw new Error(`Status ${resp.status}`);
        }
        const data = await resp.json();
        const selected = typeof data.audio_device === 'string' ? data.audio_device : null;
        const current = syncAudioSelection(data.audio_outputs, selected);
        const volumeValue = syncVolume(data.audio_volume);
        const motorValues = syncMotorLimits(data.motor_limits);
        const messageParts = [];
        let tone = '';
        if (current) {
          if (volumeValue !== null) {
            messageParts.push('Audio-Ausgabe und Lautstärke geladen');
          } else {
            messageParts.push('Audio-Ausgabe geladen (keine Lautstärke-Steuerung verfügbar)');
          }
          tone = 'success';
        } else {
          messageParts.push('Keine Audio-Ausgabegeräte verfügbar');
          tone = 'error';
        }
        if (motorValues) {
          messageParts.push('Motor-Limits geladen');
          if (!tone) {
            tone = 'success';
          }
        }
        const message = messageParts.length > 0 ? `${messageParts.join(' · ')}.` : '';
        setStatus(message, tone);
      } catch (err) {
        console.error('Laden fehlgeschlagen', err);
        setStatus('Konnte Einstellungen nicht laden.', 'error');
        audioSelect.disabled = true;
        syncMotorLimits(null);
      }
    }

    async function saveSelection(deviceId) {
      if (!deviceId) {
        return;
      }
      try {
        setStatus('Speichere …');
        const resp = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audio_device: deviceId })
        });
        if (!resp.ok) {
          throw new Error(`Status ${resp.status}`);
        }
        const data = await resp.json();
        syncAudioSelection(data.audio_outputs, data.audio_device);
        const volumeValue = syncVolume(data.audio_volume);
        syncMotorLimits(data.motor_limits);
        if (volumeValue !== null) {
          setStatus('Audio-Ausgabe und Lautstärke gespeichert.', 'success');
        } else {
          setStatus('Audio-Ausgabe gespeichert.', 'success');
        }
      } catch (err) {
        console.error('Speichern fehlgeschlagen', err);
        setStatus('Speichern fehlgeschlagen.', 'error');
      }
    }

    async function saveVolume(rawValue) {
      if (!volumeConfig) {
        return;
      }
      const value = clampVolume(rawValue);
      if (value === null) {
        return;
      }
      try {
        setStatus('Speichere Lautstärke …');
        const payload = { audio_volume: value };
        const currentDevice = audioSelect.value;
        if (currentDevice) {
          payload.audio_device = currentDevice;
        }
        const resp = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) {
          throw new Error(`Status ${resp.status}`);
        }
        const data = await resp.json();
        syncAudioSelection(data.audio_outputs, data.audio_device);
        syncMotorLimits(data.motor_limits);
        const updated = syncVolume(data.audio_volume);
        if (updated !== null) {
          setStatus('Lautstärke gespeichert.', 'success');
        } else {
          setStatus('Keine Lautstärke-Steuerung verfügbar.', 'error');
        }
      } catch (err) {
        console.error('Speichern der Lautstärke fehlgeschlagen', err);
        setStatus('Speichern der Lautstärke fehlgeschlagen.', 'error');
      }
    }

    async function saveMotorLimits(forward, reverse) {
      if (!motorForward || !motorReverse) {
        return;
      }
      try {
        setStatus('Speichere Motor-Grenzen …');
        const payload = { motor_limits: { forward, reverse } };
        const currentDevice = audioSelect.value;
        if (currentDevice) {
          payload.audio_device = currentDevice;
        }
        const resp = await fetch('/api/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) {
          throw new Error(`Status ${resp.status}`);
        }
        const data = await resp.json();
        syncAudioSelection(data.audio_outputs, data.audio_device);
        syncMotorLimits(data.motor_limits);
        syncVolume(data.audio_volume);
        setStatus('Motor-Grenzen gespeichert.', 'success');
      } catch (err) {
        console.error('Speichern der Motor-Grenzen fehlgeschlagen', err);
        setStatus('Motor-Grenzen konnten nicht gespeichert werden.', 'error');
      }
    }

    audioSelect.addEventListener('change', () => {
      const value = audioSelect.value;
      if (value) {
        saveSelection(value);
      }
    });

    if (motorForward && motorForwardValue) {
      motorForward.addEventListener('input', () => {
        const value = clampMotorFromSlider(motorForward.value);
        motorForwardValue.textContent = value === null ? '–' : formatMotorPercent(value);
      });
      motorForward.addEventListener('change', () => {
        const values = getCurrentMotorValues();
        if (!values) {
          return;
        }
        motorForward.value = String(Math.round(values.forward * 100));
        motorForwardValue.textContent = formatMotorPercent(values.forward);
        motorReverse.value = String(Math.round(values.reverse * 100));
        motorReverseValue.textContent = formatMotorPercent(values.reverse);
        saveMotorLimits(values.forward, values.reverse);
      });
    }

    if (motorReverse && motorReverseValue) {
      motorReverse.addEventListener('input', () => {
        const value = clampMotorFromSlider(motorReverse.value);
        motorReverseValue.textContent = value === null ? '–' : formatMotorPercent(value);
      });
      motorReverse.addEventListener('change', () => {
        const values = getCurrentMotorValues();
        if (!values) {
          return;
        }
        motorForward.value = String(Math.round(values.forward * 100));
        motorForwardValue.textContent = formatMotorPercent(values.forward);
        motorReverse.value = String(Math.round(values.reverse * 100));
        motorReverseValue.textContent = formatMotorPercent(values.reverse);
        saveMotorLimits(values.forward, values.reverse);
      });
    }

    if (volumeSlider) {
      volumeSlider.addEventListener('input', () => {
        volumeValue.textContent = formatVolume(volumeSlider.value);
      });
      volumeSlider.addEventListener('change', () => {
        const value = clampVolume(volumeSlider.value);
        if (value !== null) {
          saveVolume(value);
        }
      });
    }

    loadState();
  </script>
</body>
</html>"""

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
            self._write_response(200, self.HTML_PAGE)
            return
        if self.path == "/settings":
            self._write_response(200, self.SETTINGS_PAGE)
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

def set_motor(pi, speed_norm):
    s = clamp(speed_norm, -1.0, +1.0)
    if abs(s) < 1e-3:
        pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, 0)
        return
    direction = 1 if s > 0 else 0
    pi.write(GPIO_PIN_MOTOR_DIR, direction)
    duty = int(abs(s) * 1_000_000)   # pigpio hardware_PWM erwartet 0..1_000_000
    pi.hardware_PWM(GPIO_PIN_MOTOR_PWM, PWM_FREQ_HZ, duty)


# --------- Main ---------
def main():
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

    head_current = clamp(HEAD_CENTER_DEG, HEAD_MIN_DEG, HEAD_MAX_DEG)
    head_target  = head_current
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
            max_du = RATE_UNITS_S * dt
            step_u = clamp(filtered_motor - motor_speed, -max_du, +max_du)
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
            head_filtered = head_current + (head_target - head_current) * HEAD_SMOOTH_A
            head_max_step = HEAD_RATE_DEG_S * dt
            head_step     = clamp(head_filtered - head_current, -head_max_step, +head_max_step)
            head_current += head_step
            pi.set_servo_pulsewidth(GPIO_PIN_HEAD, deg_to_us_unclamped(head_current))

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
