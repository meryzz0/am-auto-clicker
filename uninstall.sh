#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run ./uninstall.sh as your normal user. It will ask for sudo when needed."
  exit 1
fi

HOME_DIR="$HOME"
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
USER_NAME="$(id -un)"
INPUT_GROUP="am-auto-clicker-input"
BIN_DIR="$HOME_DIR/.local/bin"
CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME_DIR/.config}"
CONFIG_DIR="$CONFIG_ROOT/am-auto-clicker"
PATH_FILE="$CONFIG_DIR/keybinding-path"

# Ask the running app to stop and release the virtual mouse before removing it.
if [[ -x "$BIN_DIR/am-auto-clicker" ]]; then
  "$BIN_DIR/am-auto-clicker" --quit >/dev/null 2>&1 || true
  sleep 0.2
fi

SHORTCUT_CLEANUP_OK=true
printf 'Removing the GNOME global shortcut…\n'
if [[ -f "$PATH_FILE" ]]; then
  if ! command -v gsettings >/dev/null 2>&1; then
    echo "gsettings is unavailable; preserving the shortcut marker for a later cleanup attempt."
    SHORTCUT_CLEANUP_OK=false
  else
    if ! python3 - "$PATH_FILE" "$BIN_DIR/am-auto-clicker" <<'PY'
import ast
import pathlib
import re
import shlex
import subprocess
import sys

path_file = pathlib.Path(sys.argv[1])
binary = pathlib.Path(sys.argv[2])
base = "org.gnome.settings-daemon.plugins.media-keys"
prefix = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def run(args):
    return subprocess.run(args, text=True, capture_output=True, check=True, timeout=4).stdout.strip()

def gsettings_string(schema, key):
    value = run(["gsettings", "get", schema, key]).strip()
    if value.startswith("@s "):
        value = value[3:]
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, str):
        raise ValueError(f"GNOME returned an invalid value for {key}")
    return parsed

try:
    owned_path = path_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(re.escape(prefix) + r"custom[0-9]+/", owned_path):
        raise ValueError("Saved shortcut path has an invalid format; leaving GNOME shortcuts unchanged.")

    schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + owned_path
    name = gsettings_string(schema, "name")
    command = shlex.split(gsettings_string(schema, "command"))
    if name != "AM Auto Clicker: Toggle" or command != [str(binary), "--toggle"]:
        raise ValueError("The saved shortcut no longer matches AM Auto Clicker; leaving it unchanged.")
    else:
        raw = run(["gsettings", "get", base, "custom-keybindings"])
        if raw.startswith("@as "):
            raw = raw[4:]
        paths = ast.literal_eval(raw)
        if owned_path in paths:
            paths.remove(owned_path)
            def quote(value):
                return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
            value = "[" + ", ".join(quote(item) for item in paths) + "]"
            run(["gsettings", "set", base, "custom-keybindings", value])
except Exception as exc:
    print(f"Could not remove the global shortcut automatically: {exc}", file=sys.stderr)
    sys.exit(1)
PY
    then
      SHORTCUT_CLEANUP_OK=false
    fi
  fi
fi

printf 'Removing the input-device rule…\n'
remove_managed_file() {
  local path="$1" expected="$2" description="$3" current
  if ! sudo test -e "$path"; then
    return 0
  fi
  current="$(sudo cat -- "$path" 2>/dev/null || true)"
  if [[ "$current" == "$expected" ]]; then
    sudo rm -f -- "$path"
    printf 'Removed %s.\n' "$description"
  else
    printf 'Leaving %s unchanged because its contents no longer match the AM Auto Clicker template: %s\n' "$description" "$path"
  fi
}
remove_managed_file /etc/udev/rules.d/70-am-auto-clicker-uinput.rules "$UDEV_RULE_CONTENT" "AM Auto Clicker udev rule"
remove_managed_file "$MODULE_CONFIG" "$MODULE_CONFIG_CONTENT" "AM Auto Clicker module configuration"
sudo udevadm control --reload-rules || true
sudo udevadm trigger --sysname-match=uinput || true
if getent group "$INPUT_GROUP" >/dev/null; then
  sudo gpasswd -d "$USER_NAME" "$INPUT_GROUP" >/dev/null 2>&1 || true
  if ! getent group "$INPUT_GROUP" | awk -F: '{print $4}' | grep -q '[^,]'; then
    sudo groupdel "$INPUT_GROUP" >/dev/null 2>&1 || true
  else
    echo "The $INPUT_GROUP group still has other members, so it was left in place."
  fi
fi

rm -rf "$DATA_HOME/am-auto-clicker" \
       "$DATA_HOME/applications/com.am.autoclicker.desktop" \
       "$DATA_HOME/icons/hicolor/scalable/apps/com.am.autoclicker.svg" \
       "$BIN_DIR/am-auto-clicker"
if [[ "$SHORTCUT_CLEANUP_OK" == true ]]; then
  rm -f "$PATH_FILE"
else
  echo "The GNOME shortcut marker was preserved at $PATH_FILE so its ownership can be checked again later."
fi

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

cat <<'EOF'
AM Auto Clicker has been removed.
Your saved preferences and log files were kept. Sign out and back in to refresh group membership.
EOF
if [[ "$SHORTCUT_CLEANUP_OK" != true ]]; then
  echo "Warning: review the GNOME global shortcut manually; automatic removal was not confirmed."
fi
