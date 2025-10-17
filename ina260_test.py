"""Kleines Diagnoseskript für den INA260-Stromsensor.

Dieses Skript prüft, ob der Sensor auf dem I2C-Bus erreichbar ist und
liest einige Beispielwerte aus. Es eignet sich zum Einsatz auf einem
Raspberry Pi oder vergleichbaren Systemen mit CircuitPython-Bibliotheken.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional, Tuple


class I2CLockTimeout(RuntimeError):
    """Signals that the I2C bus could not be locked within the timeout."""


def require_modules() -> Tuple[object, object]:
    """Lädt die benötigten Bibliotheken und gibt sie zurück."""

    import board  # type: ignore
    import adafruit_ina260  # type: ignore

    return board, adafruit_ina260


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose für INA260 Sensor")
    parser.add_argument(
        "--address",
        type=lambda value: int(value, 0),
        default=0x40,
        help=(
            "I2C-Adresse des Sensors (Standard 0x40). Der Wert kann dezimal, "
            "hexadezimal (z. B. 0x40) oder oktal angegeben werden."
        ),
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Anzahl der Messwerte, die gelesen werden sollen.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Sekunden zwischen den Messungen.",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=5.0,
        help="Sekunden, die maximal auf einen freien I2C-Bus gewartet werden.",
    )
    return parser.parse_args(argv)


def wait_for_i2c_lock(i2c: object, timeout_s: float) -> None:
    """Wartet auf einen freien I2C-Bus oder wirft einen Fehler."""

    start = time.monotonic()
    while not i2c.try_lock():
        if time.monotonic() - start >= timeout_s:
            raise I2CLockTimeout(
                f"I2C-Bus konnte innerhalb von {timeout_s:.1f} Sekunden nicht gesperrt werden."
            )
        time.sleep(0.01)


def main(argv: Optional[list[str]] = None) -> int:
    try:
        board, adafruit_ina260 = require_modules()
    except ModuleNotFoundError as exc:
        print(
            "Bibliotheken konnten nicht geladen werden. Stellen Sie sicher, dass\n"
            "'adafruit-circuitpython-ina260' und 'adafruit-blinka' installiert sind.\n"
            f"Originalfehler: {exc}",
            file=sys.stderr,
        )
        return 1

    args = parse_args(argv)

    print("Initialisiere I2C-Bus ...")
    try:
        i2c = board.I2C()  # type: ignore[attr-defined]
    except Exception as exc:
        print(f"I2C-Bus konnte nicht initialisiert werden: {exc}", file=sys.stderr)
        return 2

    # Auf den Bus warten, bis er bereit ist
    try:
        wait_for_i2c_lock(i2c, args.lock_timeout)
    except I2CLockTimeout as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        devices = i2c.scan()
        if args.address not in devices:
            print(
                "Warnung: Die I2C-Adresse 0x{0:02X} wurde nicht gefunden.\n"
                "Gefundene Adressen: {1}".format(args.address, [hex(dev) for dev in devices])
            )
        else:
            print(f"Sensor unter 0x{args.address:02X} gefunden.")
    finally:
        i2c.unlock()

    print("Initialisiere INA260 ...")
    try:
        sensor = adafruit_ina260.INA260(i2c, address=args.address)
    except Exception as exc:
        print(f"INA260 konnte nicht initialisiert werden: {exc}", file=sys.stderr)
        return 3

    try:
        sensor.average_count = adafruit_ina260.AveragingCount.COUNT_16
    except Exception:
        pass
    try:
        sensor.mode = adafruit_ina260.Mode.CONTINUOUS
    except Exception:
        pass

    print("Lese Messwerte ...")
    try:
        for idx in range(1, args.samples + 1):
            try:
                voltage = float(sensor.voltage)
                current_ma = float(sensor.current)
                power_mw = float(sensor.power)
            except Exception as exc:
                print(f"Fehler beim Lesen: {exc}", file=sys.stderr)
                return 4

            print(
                "#{idx}: Spannung = {voltage:.3f} V, Strom = {current_ma/1000:.3f} A, Leistung = {power_mw/1000:.3f} W".format(
                    idx=idx,
                    voltage=voltage,
                    current_ma=current_ma,
                    power_mw=power_mw,
                )
            )
            time.sleep(max(0.0, args.delay))
    except KeyboardInterrupt:
        print("Abgebrochen durch Benutzer.")
        return 130

    print("Fertig.")
    return 0


if __name__ == "__main__":  # pragma: no cover - Script-Einstiegspunkt
    raise SystemExit(main())
