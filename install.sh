#!/usr/bin/env bash
set -Eeuo pipefail

INPUT_GROUP="am-auto-clicker-input"
USER_NAME="$(id -un)"
HOME_DIR="$HOME"
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$DATA_HOME/am-auto-clicker"
BIN_DIR="$HOME_DIR/.local/bin"
APPS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME_DIR/.config}"
CONFIG_DIR="$CONFIG_ROOT/am-auto-clicker"
UDEV_RULE="/etc/udev/rules.d/70-am-auto-clicker-uinput.rules"
MODULE_CONFIG="/etc/modules-load.d/am-auto-clicker-uinput.conf"
UDEV_RULE_CONTENT='# Managed by AM Auto Clicker. Remove with uninstall.sh.
KERNEL=="uinput", GROUP="am-auto-clicker-input", MODE="0660", OPTIONS+="static_node=uinput"'
MODULE_CONFIG_CONTENT='# Managed by AM Auto Clicker. Remove with uninstall.sh.
uinput'

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run ./install.sh as your normal user. The installer will ask for sudo when needed."
  exit 1
fi
if [[ ! -d "$SOURCE_DIR/src/am_auto_clicker" || ! -f "$SOURCE_DIR/data/com.am.autoclicker.desktop" ]]; then
  echo "The project files are incomplete. Extract the full ZIP before running this installer."
  exit 1
fi
command -v apt-get >/dev/null || { echo "This installer requires an Ubuntu-based system with APT, such as Zorin OS."; exit 1; }
command -v gsettings >/dev/null || { echo "gsettings was not found. Open a GNOME desktop session and try again."; exit 1; }

cat <<'EOF'
AM Auto Clicker needs to install system packages and configure access to /dev/uinput.
It will create the dedicated am-auto-clicker-input group, add your user to it,
and install a udev rule for that group. The app itself will not run as root.
EOF
read -r -p "Continue with installation? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]; then
  echo "Installation cancelled. No changes were made."
  exit 0
fi

# Never overwrite a pre-existing system configuration that is not ours.
for managed_file in "$UDEV_RULE" "$MODULE_CONFIG"; do
  if sudo test -e "$managed_file"; then
    if [[ "$managed_file" == "$UDEV_RULE" ]]; then
      expected="$UDEV_RULE_CONTENT"
    else
      expected="$MODULE_CONFIG_CONTENT"
    fi
    current="$(sudo cat -- "$managed_file" 2>/dev/null || true)"
    if [[ "$current" != "$expected" ]]; then
      echo "Refusing to overwrite an existing system file that differs from AM Auto Clicker's expected configuration: $managed_file"
      echo "Review that file manually, then rerun the installer. No package or device configuration changes have been made yet."
      exit 1
    fi
  fi
done

printf '\n[1/5] Installing system packages…\n'
sudo apt-get update
sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-evdev

printf '\n[2/5] Setting up the virtual mouse device…\n'
if ! getent group "$INPUT_GROUP" >/dev/null; then
  sudo groupadd --system "$INPUT_GROUP"
fi
sudo usermod -aG "$INPUT_GROUP" "$USER_NAME"

printf '%s\n' "$MODULE_CONFIG_CONTENT" | sudo tee "$MODULE_CONFIG" >/dev/null
printf '%s\n' "$UDEV_RULE_CONTENT" | sudo tee "$UDEV_RULE" >/dev/null
sudo modprobe uinput
sudo udevadm control --reload-rules
sudo udevadm trigger --sysname-match=uinput || true
if [[ -e /dev/uinput ]]; then
  sudo chgrp "$INPUT_GROUP" /dev/uinput
  sudo chmod 0660 /dev/uinput
else
  echo "Warning: /dev/uinput was not created. The app will explain how to fix this when launched."
fi


printf '\n[3/5] Installing AM Auto Clicker…\n'
mkdir -p "$APP_DIR/src" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR" "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
rm -rf "$APP_DIR/src/am_auto_clicker"
cp -a "$SOURCE_DIR/src/am_auto_clicker" "$APP_DIR/src/"
cp "$SOURCE_DIR/data/com.am.autoclicker.svg" "$ICON_DIR/com.am.autoclicker.svg"
chmod 644 "$ICON_DIR/com.am.autoclicker.svg"

python3 - "$APP_DIR" "$BIN_DIR/am-auto-clicker" <<'PY_LAUNCHER'
import pathlib
import shlex
import sys

app_dir = pathlib.Path(sys.argv[1])
launcher = pathlib.Path(sys.argv[2])
# shlex.quote creates a safe literal for the generated POSIX shell script.
app_path = shlex.quote(str(app_dir / "src"))
launcher.write_text(
    "#!/usr/bin/env sh\n"
    f"APP_SOURCE={app_path}\n"
    'export PYTHONPATH="$APP_SOURCE${PYTHONPATH:+:$PYTHONPATH}"\n'
    'exec /usr/bin/python3 -m am_auto_clicker "$@"\n',
    encoding="utf-8",
)
launcher.chmod(0o755)
PY_LAUNCHER

# Write a desktop launcher using the user's actual home path (not a PATH-dependent Exec).
python3 - "$SOURCE_DIR/data/com.am.autoclicker.desktop" "$APPS_DIR/com.am.autoclicker.desktop" "$BIN_DIR/am-auto-clicker" <<'PY_DESKTOP'
from pathlib import Path
import sys

source, target, executable = map(Path, sys.argv[1:])
contents = source.read_text(encoding="utf-8")
# Desktop Entry Exec syntax supports a quoted executable; escape quotes and backslashes.
exec_path = str(executable).replace("\\", "\\\\").replace('"', '\\"')
lines = [f'Exec="{exec_path}" --show' if line.startswith("Exec=") else line
         for line in contents.splitlines()]
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
target.chmod(0o644)
PY_DESKTOP

printf '\n[4/5] Configuring the global shortcut…\n'
python3 - "$HOME_DIR" "$BIN_DIR/am-auto-clicker" <<'PY'
import ast
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys

home = pathlib.Path(sys.argv[1])
binary = pathlib.Path(sys.argv[2])
config_root = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
config_dir = config_root / "am-auto-clicker"
config_file = config_dir / "config.json"
path_file = config_dir / "keybinding-path"
base = "org.gnome.settings-daemon.plugins.media-keys"
prefix = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def run(args):
    result = subprocess.run(["gsettings", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=4)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "gsettings failed")
    return result.stdout.strip()

def quote(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

def decode_array(value):
    value = value.strip()
    if value.startswith("@as "):
        value = value[4:]
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("GNOME returned an invalid custom-keybindings array")
    return parsed

def get_value(schema, key):
    raw = run(["get", schema, key]).strip()
    if raw.startswith("@s "):
        raw = raw[3:]
    value = ast.literal_eval(raw)
    if not isinstance(value, str):
        raise ValueError(f"GNOME returned an invalid string for {key}")
    return value

try:
    data = {}
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    binding = data.get("hotkey", "F6") if isinstance(data, dict) else "F6"
    if not isinstance(binding, str) or not binding.strip():
        binding = "F6"

    paths = decode_array(run(["get", base, "custom-keybindings"]))
    saved_path = path_file.read_text(encoding="utf-8").strip() if path_file.exists() else ""
    path = ""
    if re.fullmatch(re.escape(prefix) + r"custom[0-9]+/", saved_path) and saved_path in paths:
        schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + saved_path
        try:
            existing_name = get_value(schema, "name")
            existing_command = shlex.split(get_value(schema, "command"))
            if existing_name == "AM Auto Clicker: Toggle" and existing_command == [str(binary), "--toggle"]:
                path = saved_path
        except Exception:
            path = ""

    if not path:
        index = 0
        occupied = set(paths)
        while True:
            candidate = f"{prefix}custom{index}/"
            if candidate not in occupied:
                path = candidate
                break
            index += 1
        paths.append(path)

    run(["set", base, "custom-keybindings", "[" + ", ".join(quote(item) for item in paths) + "]"])
    schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + path
    run(["set", schema, "name", quote("AM Auto Clicker: Toggle")])
    command = shlex.quote(str(binary)) + " --toggle"
    run(["set", schema, "command", quote(command)])
    run(["set", schema, "binding", quote(binding)])
    path_file.write_text(path + "\n", encoding="utf-8")
    path_file.chmod(0o600)
    print(f"Global shortcut configured: {binding}")
except Exception as exc:
    print(f"Could not configure the GNOME global shortcut automatically: {exc}")
    print(f"You can set it later to: {binary} --toggle")
PY

printf '\n[5/5] Refreshing the application menu…\n'
if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

cat <<'EOF'

Installation complete.

Next steps:
  1. Sign out of Zorin and sign back in so the uinput group permission takes effect.
  2. Open “AM Auto Clicker” from the applications menu.
  3. Open your target application, position the pointer, and use the displayed global shortcut.
  4. Press the same shortcut again to stop.

The app runs as your normal user. Only /dev/uinput receives the dedicated group permission.
EOF
