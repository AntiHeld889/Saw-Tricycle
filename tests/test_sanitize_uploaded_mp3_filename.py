from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


class _FakeEcodes:
    ecodes = {}

    def __getattr__(self, _name: str) -> int | None:
        return None


def _ensure_test_dependencies() -> None:
    if "evdev" not in sys.modules:
        fake_evdev = types.SimpleNamespace(
            InputDevice=object,
            ecodes=_FakeEcodes(),
            list_devices=lambda: [],
        )
        sys.modules["evdev"] = fake_evdev
    if "pigpio" not in sys.modules:
        class _DummyPi:
            connected = True

            def set_mode(self, *args, **kwargs) -> None:
                pass

            def write(self, *args, **kwargs) -> None:
                pass

            def hardware_PWM(self, *args, **kwargs) -> None:
                pass

            def set_servo_pulsewidth(self, *args, **kwargs) -> None:
                pass

        def _make_pi() -> _DummyPi:
            return _DummyPi()

        fake_pigpio = types.SimpleNamespace(
            OUTPUT=0,
            pi=_make_pi,
            set_servo_pulsewidth=lambda *args, **kwargs: None,
        )
        sys.modules["pigpio"] = fake_pigpio


_ensure_test_dependencies()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tricycle import sanitize_uploaded_mp3_filename


class SanitizeUploadedMp3FilenameTests(unittest.TestCase):
    def test_truncates_long_ascii_names_within_byte_limit(self) -> None:
        name = "a" * 300 + ".mp3"
        result = sanitize_uploaded_mp3_filename(name)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".mp3"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_truncates_multibyte_names_within_byte_limit(self) -> None:
        name = "ä" * 200 + ".mp3"
        result = sanitize_uploaded_mp3_filename(name)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".mp3"))
        self.assertLessEqual(len(result.encode("utf-8")), 255)

    def test_accepts_bytes_input(self) -> None:
        name = ("ä" * 5 + " valid name" + ".mp3").encode("utf-8")
        result = sanitize_uploaded_mp3_filename(name)
        self.assertEqual(result, "ä" * 5 + " valid name" + ".mp3")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
