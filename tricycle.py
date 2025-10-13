#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =========================
#   KONFIGURATION (OBEN)
# =========================

# ---- Audio & Dateien ----
START_MP3_PATH       = "/opt/python/sawsounds/Start.mp3"   # Pfad anpassen falls nötig
ALSA_HP_DEVICE       = "plughw:0,0"           # Analoger Kopfhörer-Ausgang (mit 'aplay -l' prüfen)
HEADPHONE_VOLUME     = "100%"
AUDIO_ROUTE_TIMEOUT  = 3                      # Sekunden für amixer-Kommandos

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
import os
import sys
import time
import subprocess

from evdev import InputDevice, ecodes, list_devices
import pigpio


# === Laufzeit-Handle für exklusives MP3-Playback ===
CURRENT_PLAYER_PROC = None
CURRENT_PLAYER_PATH = None


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


# --------- Audio-Helper ---------
def route_audio_to_headphones():
    """Route Audio → Kopfhörerbuchse & setze Lautstärke."""
    cmds = [
        ["amixer", "-q", "cset", "numid=3", "1"],             # 0=auto, 1=analog, 2=HDMI (älteres RPi-OS)
        ["amixer", "-q", "sset", "Headphone", HEADPHONE_VOLUME],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=False, timeout=AUDIO_ROUTE_TIMEOUT)
        except Exception:
            pass

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

    # Gamepad
    dev = find_gamepad()

    # Startsound nach erfolgreicher Verbindung
    route_audio_to_headphones()
    play_sound_switch(START_MP3_PATH, ALSA_HP_DEVICE)

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
                            play_sound_switch(SOUND_KEY_MAP[e.code], ALSA_HP_DEVICE)
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
            if motor_speed > 0:
                motor_speed = min(motor_speed, MOTOR_LIMIT_FWD)
            elif motor_speed < 0:
                motor_speed = max(motor_speed, -MOTOR_LIMIT_REV)

            set_motor(pi, motor_speed)

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


if __name__ == "__main__":
    main()
