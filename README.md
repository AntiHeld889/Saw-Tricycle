# Saw Tricycle Steuerung (Neuimplementierung)

Dieses Verzeichnis enthält die modulare Neuimplementierung der Saw-Tricycle-Steuerung
für einen Raspberry Pi mit Raspberry Pi OS (Bookworm). Die Hardware-Pinbelegung und
Servo-Winkel bleiben identisch zur ursprünglichen Version.

## 1. Voraussetzungen installieren (Raspberry Pi OS Bookworm)

```bash
sudo apt update
sudo apt install \
    python3 python3-venv python3-pip \
    python3-evdev python3-pigpio \
    git mpg123 alsa-utils
```

* `python3-evdev` und `python3-pigpio` stellen die Kernel-/GPIO-Bindings bereit.
* `pigpiod` wird mit `python3-pigpio` installiert; aktivieren Sie den Dienst später.
* `mpg123` und `alsa-utils` werden für die Audiowiedergabe und Lautstärkesteuerung benötigt.

## 2. Quellcode beziehen und virtuelles Environment anlegen

```bash
cd /opt
sudo git clone https://github.com/<Ihr-Konto>/Saw-Tricycle.git
sudo chown -R $USER:$USER Saw-Tricycle
cd Saw-Tricycle
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn pigpio evdev
```

> **Hinweis:** Die Steuerung funktioniert auch ohne installierte FastAPI-Module,
> allerdings steht die optionale Status-API dann nicht zur Verfügung.

## 3. pigpiod aktivieren

Der `pigpiod`-Daemon muss laufen, damit Servos und Motor über die pigpio-Bibliothek
angesprochen werden können.

```bash
sudo systemctl enable --now pigpiod.service
```

## 4. Programm starten

* Spiele-Sounds nach `/opt/python/sawsounds/` kopieren (Dateinamen wie im ursprünglichen
  Projekt beibehalten).
* Gamepad per USB-Dongle oder Bluetooth koppeln.
* Virtuelles Environment aktivieren (`source /opt/Saw-Tricycle/.venv/bin/activate`).
* Anschließend:

```bash
python -m saw_tricycle
```

Die Anwendung initialisiert Gamepad, Motor, Servos und Audio. Log-Ausgaben erscheinen auf der Konsole.

## 5. Optional: Status-API/Webserver starten

Der modulare Aufbau enthält eine kleine FastAPI-Anwendung zur Telemetrie. Sie wird nicht automatisch
aus `python -m saw_tricycle` heraus gestartet, kann aber in einem eigenen Prozess betrieben werden.
Ein Minimalbeispiel, das eine vorhandene `TricycleState`-Instanz veröffentlicht, könnte so aussehen:

```bash
python - <<'PY'
from saw_tricycle.web.server import WebServer
from saw_tricycle.state import TricycleState, ServoState

state = TricycleState(
    steering=ServoState(angle_deg=0.0, target_deg=0.0),
    head=ServoState(angle_deg=0.0, target_deg=0.0),
)

server = WebServer()
server.bind_state(state)
server.run(host="0.0.0.0", port=8000)
PY
```

In einer produktiven Umgebung sollte der Webserver aus demselben Prozess wie die Steuerung
heraus gebunden werden (z. B. via zusätzlichem Supervisor-Task im Async-Loop).

## 6. Systemd-Service einrichten

Erstellen Sie eine Service-Datei `/etc/systemd/system/saw-tricycle.service` mit folgendem Inhalt
(ggf. Pfade anpassen):

```ini
[Unit]
Description=Saw Tricycle Control Stack
After=network-online.target pigpiod.service
Wants=network-online.target pigpiod.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/Saw-Tricycle
Environment="PATH=/opt/Saw-Tricycle/.venv/bin"
ExecStart=/opt/Saw-Tricycle/.venv/bin/python -m saw_tricycle
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Service aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now saw-tricycle.service
```

Logs lassen sich später mit `journalctl -u saw-tricycle.service -f` verfolgen.

## 7. Datenverzeichnis vorbereiten

Standardmäßig nutzt die Anwendung `/var/lib/saw-tricycle` zur Ablage von Laufzeitdaten.
Legen Sie das Verzeichnis mit passenden Rechten an:

```bash
sudo mkdir -p /var/lib/saw-tricycle
sudo chown pi:pi /var/lib/saw-tricycle
```

## 8. Fehlerdiagnose

* Prüfen, ob `pigpiod` läuft: `systemctl status pigpiod`.
* Gamepad-Geräteliste: `python -m evdev.evtest`.
* Audioausgabe testen: `mpg123 /opt/python/sawsounds/Start.mp3`.

Viel Erfolg bei der Inbetriebnahme der neuen Steuerungssoftware!
