# Architecture

AM Auto Clicker is a small Python desktop application organized by responsibility.

- `app.py` is the command-line entry point. It handles `--help` and `--version` before importing GTK, and configures a rotating log in the user's XDG state directory.
- `application.py` owns the single-instance `Adw.Application` and routes `--show`, `--toggle`, and `--quit` requests.
- `window.py` builds the GTK 4 / Libadwaita interface, validates user interactions, and coordinates state changes with the click worker.
- `click_engine.py` creates a virtual input device through `python-evdev`, emits mouse-button events on a worker thread, uses interruptible waits, and attempts to release the button before closing the device.
- `config.py` validates supported values and writes JSON settings through a same-directory temporary file, `fsync`, and atomic replacement. The config file and directory are restricted to the current user.
- `shortcuts.py` formats keyboard accelerators and updates the custom GNOME shortcut installed by the setup script. Calls to `gsettings` use an argument vector rather than a shell command, and the module checks that the saved shortcut belongs to this application before changing it.
- `data/` contains the desktop entry and the project's original SVG icon.
- `install.sh` installs distribution packages and configures `/dev/uinput` access; `uninstall.sh` removes only the application's resources and its own global shortcut.

The click engine is intentionally separate from GTK so it can be tested with a fake input device. Unit tests cannot prove that every compositor or target application accepts events from a virtual input device; real desktop integration testing remains necessary.
