#!/usr/bin/env python3
"""Einfaches Testskript zum Auslesen eines INA260-Sensors."""

import sys
import time

try:
    import board
    import adafruit_ina260
except ImportError as exc:  # pragma: no cover - abhängig von Hardware-Setup
    print(
        "Fehler: Benötigte Bibliotheken konnten nicht importiert werden:"
        f" {exc}.\n"
        "Installiere 'adafruit-circuitpython-ina260' und stelle sicher, dass"
        " I2C aktiviert ist.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    """Initialisiert den Sensor und gibt laufend Messwerte aus."""
    try:
        i2c = board.I2C()  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - abhängig von Hardware-Setup
        print(f"Konnte I2C-Bus nicht initialisieren: {exc}", file=sys.stderr)
        return 1

    try:
        sensor = adafruit_ina260.INA260(i2c)  # type: ignore[call-arg]
        try:
            sensor.average_count = adafruit_ina260.AveragingCount.COUNT_16  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            sensor.mode = adafruit_ina260.Mode.CONTINUOUS  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - abhängig von Hardware-Setup
        print(f"INA260 konnte nicht initialisiert werden: {exc}", file=sys.stderr)
        return 1

    print("INA260 Messwerte (Spannung [V], Strom [mA], Leistung [mW]) – Abbruch mit Ctrl+C")

    try:
        while True:
            try:
                voltage = sensor.bus_voltage
                current = sensor.current
                power = sensor.power
            except Exception as exc:
                print(f"Fehler beim Auslesen: {exc}", file=sys.stderr)
                return 1

            print(f"U={voltage:5.2f} V  I={current:7.2f} mA  P={power:7.2f} mW")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
