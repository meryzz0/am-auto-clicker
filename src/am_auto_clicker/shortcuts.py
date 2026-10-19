"""GNOME custom-keybinding helpers kept separate from the UI."""
from __future__ import annotations

import ast
import os
import re
import shlex
import subprocess
from pathlib import Path

SCHEMA_BASE = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

KEY_LABELS = {
    "minus": "-", "equal": "=", "plus": "+", "space": "Space",
    "Return": "Enter", "KP_Enter": "Numpad Enter", "Tab": "Tab",
    "Escape": "Esc", "BackSpace": "Backspace", "Delete": "Delete",
    "Insert": "Insert", "Home": "Home", "End": "End",
    "Prior": "Page Up", "Next": "Page Down", "Left": "←",
    "Right": "→", "Up": "↑", "Down": "↓", "bracketleft": "[",
    "bracketright": "]", "semicolon": ";", "apostrophe": "'",
    "comma": ",", "period": ".", "slash": "/", "backslash": "\\",
    "grave": "`", "underscore": "_",
}
MODIFIER_LABELS = {
    "Control": "Ctrl", "Primary": "Ctrl", "Alt": "Alt",
    "Shift": "Shift", "Super": "Super", "Meta": "Meta",
}


def shortcut_path_file() -> Path:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "am-auto-clicker" / "keybinding-path"


def format_binding(binding: str) -> str:
    """Format a GTK/GNOME accelerator as a readable key combination."""
    rest = binding.strip()
    modifiers: list[str] = []
    while rest.startswith("<") and ">" in rest:
        modifier, rest = rest[1:].split(">", 1)
        modifiers.append(MODIFIER_LABELS.get(modifier, modifier))
    key = KEY_LABELS.get(rest, rest)
    if len(key) == 1 and key.isalpha():
        key = key.upper()
    return " + ".join([*modifiers, key]) if modifiers else key


def _gvariant_string(value: str) -> str:
    """Quote a value as a GVariant string for gsettings (no shell is involved)."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _run_gsettings(args: list[str]) -> str:
    result = subprocess.run(
        ["gsettings", *args], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=3,
    )
    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or "gsettings returned an unknown error"
        )
        raise RuntimeError(detail)
    return result.stdout.strip()


def _read_gsettings_string(schema: str, key: str) -> str:
    """Read and parse a GVariant string without invoking a shell."""
    raw = _run_gsettings(["get", schema, key]).strip()
    if raw.startswith("@s "):
        raw = raw[3:]
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError(f"GNOME returned an invalid value for {key}.") from exc
    if not isinstance(value, str):
        raise RuntimeError(f"GNOME returned an invalid value for {key}.")
    return value


def set_global_binding(binding: str) -> None:
    """Update the shortcut created by the installer."""
    path_file = shortcut_path_file()
    try:
        path = path_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("The GNOME shortcut is not installed. Run install.sh again.") from exc

    if not re.fullmatch(re.escape(CUSTOM_PREFIX) + r"custom[0-9]+/", path):
        raise RuntimeError("The saved GNOME shortcut path is invalid. Run install.sh again.")

    schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
    name = _read_gsettings_string(schema, "name")
    command = shlex.split(_read_gsettings_string(schema, "command"))
    expected_command = [str(Path.home() / ".local/bin/am-auto-clicker"), "--toggle"]
    if name != "AM Auto Clicker: Toggle" or command != expected_command:
        raise RuntimeError(
            "The saved shortcut does not belong to AM Auto Clicker. Run install.sh again."
        )

    _run_gsettings(["set", schema, "binding", _gvariant_string(binding)])


def describe_hotkey_error(error: Exception) -> str:
    message = str(error).strip()
    if "No such schema" in message or "not installed" in message:
        return (
            "The GNOME shortcut could not be found. Close the app, run install.sh again, "
            "then sign out and back in."
        )
    if "already in use" in message or "conflict" in message.lower():
        return (
            "That shortcut may already be used by GNOME or another app. "
            "Try a different key combination."
        )
    return (
        "Could not update the global shortcut. Try another key or run install.sh again."
        f"\n\nDetails: {message}"
    )
