from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def load_asset(name: str) -> str:
    """Return the contents of a bundled web asset."""
    base = Path(__file__).resolve().parent
    path = base / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown web asset: {name}")
    return path.read_text(encoding="utf-8")


__all__ = ["load_asset"]
