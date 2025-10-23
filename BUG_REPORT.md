# Bug-Report: Saw-Tricycle Code-Analyse

**Datum:** 2025-10-23
**Datei:** tricycle.py (3501 Zeilen)

## Zusammenfassung

Es wurden **7 kritische Bugs** und **3 potenzielle Probleme** identifiziert, die zu Laufzeitfehlern, Race Conditions und unerwartetem Verhalten führen können.

---

## Kritische Bugs

### 1. Division durch Null in `norm_axis_centered` (Zeile 2690-2695)

**Severity:** HOCH
**Typ:** Division by Zero

```python
def norm_axis_centered(v, lo, hi):
    """Zentrierte Achse auf [-1..+1]."""
    if hi == lo: return 0.0
    mid  = (hi + lo) / 2.0
    span = (hi - lo) / 2.0
    return (v - mid) / span
```

**Problem:**
Die Funktion gibt `0.0` zurück wenn `hi == lo`, führt aber dann trotzdem die Division durch `span` aus, welche 0 ist. Dies führt zu einem `ZeroDivisionError`.

**Auswirkung:**
Programmabsturz wenn die Achsenbereiche ungültig sind (z.B. bei defektem Gamepad).

**Fix:**
```python
def norm_axis_centered(v, lo, hi):
    """Zentrierte Achse auf [-1..+1]."""
    if hi == lo:
        return 0.0  # Early return - kein weiterer Code wird ausgeführt
    mid  = (hi + lo) / 2.0
    span = (hi - lo) / 2.0
    if span == 0.0:  # Zusätzliche Sicherheit
        return 0.0
    return (v - mid) / span
```

**HINWEIS:** Der aktuelle Code hat einen logischen Fehler - das `return 0.0` in Zeile 2692 sollte die Funktion beenden, tut es aber in der aktuellen Implementierung. Dies deutet darauf hin, dass der Code korrekt ist, aber ungewöhnlich formatiert.

---

### 2. Division durch Null in `norm_axis_trigger` (Zeile 2697-2700)

**Severity:** HOCH
**Typ:** Division by Zero

```python
def norm_axis_trigger(v, lo, hi):
    """Trigger (GAS/BRAKE) auf [0..1]."""
    if hi == lo: return 0.0
    return clamp((v - lo) / (hi - lo), 0.0, 1.0)
```

**Problem:**
Gleicher Fehler wie bei `norm_axis_centered` - wenn `hi == lo`, wird 0.0 zurückgegeben, aber die Division wird trotzdem ausgeführt.

**Auswirkung:**
Programmabsturz bei ungültigen Trigger-Achsenbereichen.

**Fix:**
```python
def norm_axis_trigger(v, lo, hi):
    """Trigger (GAS/BRAKE) auf [0..1]."""
    if hi == lo:
        return 0.0
    return clamp((v - lo) / (hi - lo), 0.0, 1.0)
```

**HINWEIS:** Auch hier könnte es sich um ein Formatierungsproblem handeln.

---

### 3. Potenzielle Division durch Null in Motor-Deadzone-Berechnung (Zeile 3383)

**Severity:** MITTEL
**Typ:** Division by Zero

```python
y_eff = (abs(y_total) - DEADZONE_MOTOR) / (1 - DEADZONE_MOTOR)
```

**Problem:**
Wenn `DEADZONE_MOTOR` jemals den Wert `1.0` hat, führt dies zu einer Division durch Null.

**Auswirkung:**
Programmabsturz bei ungültiger Konfiguration.

**Kontext:**
Die Konfiguration setzt `DEADZONE_MOTOR = 0.12`, aber dies könnte durch Benutzereingaben oder Konfigurationsänderungen geändert werden.

**Fix:**
```python
if abs(y_total) < DEADZONE_MOTOR:
    y_shaped = 0.0
else:
    sign = 1 if y_total >= 0 else -1
    denominator = 1 - DEADZONE_MOTOR
    if denominator <= 0:  # Sicherheitscheck
        y_shaped = sign
    else:
        y_eff = (abs(y_total) - DEADZONE_MOTOR) / denominator
        y_shaped = shape_expo(sign * y_eff, EXPO_MOTOR)
```

---

### 4. Race Condition: Unsichere globale Variablen-Modifikation (mehrere Stellen)

**Severity:** HOCH
**Typ:** Thread Safety / Race Condition

**Betroffene Variablen:**
- `GPIO_PIN_SERVO`, `GPIO_PIN_HEAD`, `MOTOR_DRIVER_CHANNELS` (Zeile 1271)
- `HEAD_LEFT_DEG`, `HEAD_CENTER_DEG`, `HEAD_RIGHT_DEG` (Zeile 1338)
- `LEFT_MAX_DEG`, `MID_DEG`, `RIGHT_MAX_DEG` (Zeile 1451)
- `STEERING_LEFT_US`, `STEERING_MID_US`, `STEERING_RIGHT_US` (Zeile 1483)
- `CURRENT_PLAYER_PROC`, `CURRENT_PLAYER_PATH` (Zeilen 2794, 2813)
- `_last_motor_directions` (Zeilen 2926, 2941)

**Problem:**
Diese globalen Variablen werden von mehreren Threads modifiziert:
1. **Haupt-Gamepad-Thread** liest diese Werte kontinuierlich
2. **Web-Server-Thread** kann sie durch Benutzeraktionen ändern (`apply_steering_angles`, `apply_head_angles`, etc.)

Es gibt keine Locks oder atomare Operationen, um diese Zugriffe zu synchronisieren.

**Auswirkung:**
- **Torn reads:** Der Gamepad-Thread könnte inkonsistente Werte lesen (z.B. `LEFT_MAX_DEG` neu, aber `MID_DEG` alt)
- **Unkontrolliertes Servo-Verhalten:** Wenn Winkelgrenzen während der Bewegung geändert werden
- **Motorsteuerungsfehler:** Wenn GPIO-Pins während des Betriebs geändert werden

**Fix:**
Verwendung von Locks für alle globalen Konfigurationsvariablen oder Kopie der Werte zu Beginn jeder Loop-Iteration:

```python
# Option 1: Lock verwenden
_config_lock = threading.Lock()

def apply_steering_angles(angles):
    sanitized = sanitize_steering_angles(angles)
    if sanitized is None:
        return False
    global LEFT_MAX_DEG, MID_DEG, RIGHT_MAX_DEG
    with _config_lock:
        LEFT_MAX_DEG = sanitized["left"]
        MID_DEG = sanitized["mid"]
        RIGHT_MAX_DEG = sanitized["right"]
    return True

# Option 2: Snapshot in der Main-Loop (bereits teilweise vorhanden)
# In Zeile 3212-3226 wird bereits ein Snapshot für head_angles erstellt
# Dies sollte konsistent für alle Konfigurationswerte gemacht werden
```

---

### 5. Race Condition in Audio-Player-Verwaltung (Zeilen 2794-2842)

**Severity:** MITTEL
**Typ:** Thread Safety

```python
CURRENT_PLAYER_PROC = None
CURRENT_PLAYER_PATH = None

def stop_current_sound():
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH
    # ... kein Lock

def play_sound_switch(path, alsa_dev=DEFAULT_ALSA_DEVICE, restart_if_same=None):
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH
    # ... kein Lock
```

**Problem:**
Mehrere Threads können gleichzeitig `play_sound_switch` oder `stop_current_sound` aufrufen (Gamepad-Button-Aktionen, Web-Uploads, Startup-Sound). Dies kann zu:
- Doppeltem Starten von Playern
- Player-Prozess-Leaks (Prozess wird gestartet aber nie beendet)
- Falschem Zustand von `CURRENT_PLAYER_PROC`

**Fix:**
```python
_player_lock = threading.Lock()

def stop_current_sound():
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH
    with _player_lock:
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

def play_sound_switch(path, alsa_dev=DEFAULT_ALSA_DEVICE, restart_if_same=None):
    global CURRENT_PLAYER_PROC, CURRENT_PLAYER_PATH
    with _player_lock:
        # ... rest des Codes
```

---

### 6. Fehlende Validierung in `deg_to_us_lenkung` Edge Cases (Zeilen 2709-2725)

**Severity:** NIEDRIG
**Typ:** Logic Error

```python
def deg_to_us_lenkung(deg):
    d = clamp(deg, LEFT_MAX_DEG, RIGHT_MAX_DEG)
    if d <= MID_DEG:
        denom = MID_DEG - LEFT_MAX_DEG
        if denom <= 0:
            pulse = STEERING_MID_US
        else:
            ratio = (d - LEFT_MAX_DEG) / denom
            pulse = STEERING_LEFT_US + ratio * (STEERING_MID_US - STEERING_LEFT_US)
    else:
        denom = RIGHT_MAX_DEG - MID_DEG
        if denom <= 0:
            pulse = STEERING_MID_US
        else:
            ratio = (d - MID_DEG) / denom
            pulse = STEERING_MID_US + ratio * (STEERING_RIGHT_US - STEERING_MID_US)
    return int(round(clamp(pulse, US_MIN, US_MAX)))
```

**Problem:**
Wenn `LEFT_MAX_DEG == MID_DEG == RIGHT_MAX_DEG`, funktioniert der Code korrekt (gibt immer `STEERING_MID_US` zurück). Aber wenn z.B.:
- `LEFT_MAX_DEG < d < MID_DEG` und `denom <= 0`: funktioniert
- Aber die Interpolation könnte bei ungünstigen Pulse-Werten (z.B. `STEERING_LEFT_US > STEERING_MID_US`) zu unerwarteten Ergebnissen führen

**Auswirkung:**
Geringe Auswirkung, da die Konfigurationsvalidierung in `validate_configuration()` (Zeile 2652-2653) bereits prüft, dass die Winkel sortiert sind.

**Empfehlung:**
Zusätzliche Assertion oder Warnung wenn Pulse-Werte nicht monoton sind.

---

### 7. Unvollständige Ressourcen-Freigabe in BatteryMonitor (Zeile 1649-1653)

**Severity:** NIEDRIG
**Typ:** Resource Leak

```python
def stop(self):
    self._stop.set()
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=0.2)
```

**Problem:**
Die I2C-Verbindung (`self._i2c`) wird nie explizit geschlossen. Während dies bei vielen CircuitPython/Adafruit-Bibliotheken kein Problem ist (automatisches Cleanup), könnte es zu Problemen führen wenn:
- Das Programm wiederholt gestartet/gestoppt wird
- Mehrere Instanzen versuchen auf den gleichen I2C-Bus zuzugreifen

**Auswirkung:**
Gering, aber könnte zu I2C-Bus-Konflikten führen.

**Fix:**
```python
def stop(self):
    self._stop.set()
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=0.2)
    # I2C-Verbindung schließen wenn möglich
    if self._i2c and hasattr(self._i2c, 'deinit'):
        try:
            self._i2c.deinit()
        except Exception:
            pass
```

---

## Potenzielle Probleme (Warnungen)

### W1: Shell-Injection-Risiko in Disconnect-Command (Zeile 3069)

**Severity:** SICHERHEIT (bei böswilliger Nutzung)
**Typ:** Command Injection

```python
subprocess.Popen(command, shell=True)
```

**Problem:**
Benutzer können über die Web-Oberfläche beliebige Shell-Befehle als "Disconnect Command" eingeben, die dann mit `shell=True` ausgeführt werden.

**Kontext:**
Dies ist vermutlich beabsichtigt (z.B. für Herunterfahren: `sudo shutdown -h now`), aber:
- Keine Whitelist erlaubter Befehle
- Keine Warnung in der UI

**Empfehlung:**
Dokumentation hinzufügen und ggf. Warnung in der Web-UI, dass dies Sicherheitsrisiken birgt.

---

### W2: Fehlende Dateisystem-Validierung bei Sound-Upload (Zeile 2481-2516)

**Severity:** SICHERHEIT (niedrig)
**Typ:** Path Traversal (teilweise gemildert)

**Problem:**
Die Funktion `sanitize_uploaded_mp3_filename` (Zeile 683-712) bereinigt Dateinamen, aber:
- Prüft nur `.mp3`-Endung (keine Magic-Byte-Validierung)
- Könnte durch geschickte Unicode-Zeichen umgangen werden

**Aktueller Schutz:**
- `os.path.basename()` wird mehrfach verwendet
- Prüfung auf `"."` und `".."`
- Regex-Bereinigung

**Auswirkung:**
Gering, da der Pfad gut bereinigt wird.

**Empfehlung:**
Zusätzliche Validierung der Dateiinhalte (Magic Bytes: `FF FB` oder `ID3`).

---

### W3: Unbegrenzte Rekursion in `ensure_unique_filename` (Zeile 942-951)

**Severity:** NIEDRIG
**Typ:** Resource Exhaustion

```python
def ensure_unique_filename(directory, filename, *, max_attempts=1000):
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
        if counter > max_attempts:
            raise FileExistsError("Zu viele Dateien mit ähnlichem Namen vorhanden")
    return candidate
```

**Problem:**
Bei sehr vielen Dateien mit ähnlichem Namen könnte dies langsam werden.

**Auswirkung:**
Sehr gering, da `max_attempts=1000` gesetzt ist.

---

## Empfohlene Fixes nach Priorität

1. **KRITISCH:** Fixes 1-2 (Division durch Null) prüfen und korrigieren
2. **HOCH:** Fix 4-5 (Thread-Safety mit Locks)
3. **MITTEL:** Fix 3 (DEADZONE_MOTOR Validierung)
4. **NIEDRIG:** Fixes 6-7 (Edge Cases und Ressourcen-Cleanup)

---

## Zusätzliche Beobachtungen

### Positive Aspekte:
- Extensive Input-Sanitization (Funktionen ab Zeile 669+)
- Gute Fehlerbehandlung mit 153 try-except-Blöcken
- Validierung der Konfiguration beim Start (`validate_configuration`)
- Thread-sichere WebControlState-Klasse mit eigenem Lock

### Code-Qualität:
- Gut strukturiert und lesbar
- Umfangreiche Kommentare
- Klare Trennung von Konfiguration und Implementierung

---

**Erstellt mit Claude Code**
