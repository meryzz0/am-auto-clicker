"""Validated, atomic configuration storage for AM Auto Clicker."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "interval_ms": 100,
    "button": "left",
    "limit": 0,
    "hotkey": "F6",
}
MIN_INTERVAL_MS = 10
MAX_INTERVAL_MS = 5000
MAX_CLICKS_LIMIT = 10_000_000
BUTTONS = {"left", "right", "middle"}


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "am-auto-clicker"


def config_file() -> Path:
    return config_home() / "config.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _normalise(data: dict[str, Any] | None) -> dict[str, Any]:
    result = DEFAULTS.copy()
    if not data:
        return result

    interval = data.get("interval_ms")
    if type(interval) is int:
        result["interval_ms"] = min(MAX_INTERVAL_MS, max(MIN_INTERVAL_MS, interval))

    button = data.get("button")
    if isinstance(button, str) and button in BUTTONS:
        result["button"] = button

    limit = data.get("limit")
    if type(limit) is int and limit >= 0:
        result["limit"] = min(MAX_CLICKS_LIMIT, limit)

    hotkey = data.get("hotkey")
    if isinstance(hotkey, str) and hotkey.strip() and len(hotkey) <= 100:
        result["hotkey"] = hotkey.strip()

    return result


class ConfigStore:
    """Loads validated settings and writes updates atomically with private permissions."""

    def __init__(self) -> None:
        self.path = config_file()
        self._data = _normalise(_read_json(self.path))
        self._ensure_directory()

    @property
    def data(self) -> dict[str, Any]:
        return self._data.copy()

    def update(self, **changes: Any) -> dict[str, Any]:
        previous = self._data
        self._data = _normalise(previous | changes)
        try:
            self.save()
        except Exception:
            self._data = previous
            raise
        return self.data

    def save(self) -> None:
        self._ensure_directory()
        fd, temporary_name = tempfile.mkstemp(
            prefix=".config-", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self._data, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _ensure_directory(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
