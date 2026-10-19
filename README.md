# AM Auto Clicker

A lightweight autoclicker for GNOME desktops on Linux. AM Auto Clicker uses GTK 4 and Libadwaita for its interface, a GNOME custom keyboard shortcut to toggle clicking, and Linux `uinput` to send mouse-button events through a virtual input device.

[![CI](https://github.com/meryzz0/am-auto-clicker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/meryzz0/am-auto-clicker/actions/workflows/ci.yml) [![CodeQL](https://github.com/meryzz0/am-auto-clicker/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/meryzz0/am-auto-clicker/actions/workflows/codeql.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Status: early public preview.** Unit tests and static checks are included, but end-to-end testing on multiple distributions and compatibility testing with individual games or Android runtimes are still needed. In particular, input delivered through `uinput` may not be accepted by every app or game.

## Features

- GTK 4 / Libadwaita desktop interface.
- Custom global start/stop shortcut, including punctuation keys such as `-` and combinations such as `Ctrl + F6`.
- Left, middle, or right mouse button.
- Configurable interval from **10 to 5,000 ms**.
- Optional click limit; set it to `0` for unlimited clicking.
- Settings stored locally with validated values, restrictive file permissions, and atomic writes.
- Separate worker thread to keep the interface responsive.
- Attempts to release the active button before closing the virtual input device.
- No telemetry and no network requests from the app itself.
- The application runs as the logged-in user, not as root.

## Supported environment

The installer targets **Ubuntu 24.04 or newer and Ubuntu-based GNOME desktops**, including compatible Zorin OS releases. Other distributions may work but are not currently covered by the installer or CI.

The app needs a GNOME session with `gsettings` and these system packages:

- `python3`
- `python3-gi`
- `gir1.2-gtk-4.0`
- `gir1.2-adw-1`
- `python3-evdev`

The installer installs those packages with APT. There is no `pip install` step.

## Install from source

1. Download and extract the project, or clone it:

   ```bash
   git clone https://github.com/meryzz0/am-auto-clicker.git
   cd am-auto-clicker
   ```

2. Run the installer as your normal user:

   ```bash
   ./install.sh
   ```

3. Review the installer's summary and confirm when prompted. It uses `sudo` to install APT packages, create a dedicated system group, enable the `uinput` module, and install a udev rule limited to that group.
4. Sign out of your desktop session and sign back in so the new group membership takes effect.
5. Open **AM Auto Clicker** from the applications menu.
6. Leave the app running, switch to the target application, position the pointer, and use the shortcut shown in the app to start or stop clicking. Use automation only where it is permitted by the target application.

The default shortcut is `F6`. Choose **Change shortcut…** to assign another key. GNOME may reserve some keys or combinations; if a shortcut does not work, try a different one.

### Why does installation need device permissions?

Linux exposes `/dev/uinput` for userspace-created input devices. The installer creates the dedicated `am-auto-clicker-input` group and grants that group access to `/dev/uinput`; it does **not** make the application run as root. Members of this group can create virtual input events, so do not add untrusted users to it. Review `SECURITY.md` before installing if you want to understand the permission trade-off.

## Use

- **Click interval:** nominal time between click starts. For example, `100 ms` is about 10 clicks per second; actual timing depends on scheduling and the receiving application.
- **Mouse button:** left, right, or middle.
- **Click limit:** `0` runs until stopped; a positive number stops after that many clicks.
- **Global shortcut:** works while the application is running, even when another window is focused. Closing AM Auto Clicker ends the shortcut handler, so keep it open while using the target app.
- **Emergency stop:** press the same global shortcut again or use the main button. The worker is designed to release the pressed button before stopping.

When clicking is started from the main window, the app briefly waits and then minimizes if it was active. Starting with the global shortcut while the target app is already focused avoids switching back to AM Auto Clicker.

## Troubleshooting

**The app says input permission is missing.** Sign out and back in after installation. Confirm that `/dev/uinput` exists and is accessible to your current user through `am-auto-clicker-input`.

**The app says the input device is missing.** Rerun `./install.sh` from the extracted source directory and inspect any reported APT, module, or udev errors.

**The click counter increases, but the target app does not react.** First test a harmless desktop control. If that works, the target runtime may be ignoring virtual input. AM Auto Clicker cannot guarantee compatibility with every game, emulator, or Android application.

**The shortcut does not work.** Keep AM Auto Clicker running and pick a shortcut that is not already assigned in GNOME's Keyboard settings.

Logs are stored at:

```text
${XDG_STATE_HOME:-~/.local/state}/am-auto-clicker/am-auto-clicker.log
```

Settings are stored at:

```text
${XDG_CONFIG_HOME:-~/.config}/am-auto-clicker/config.json
```

## Uninstall

From the extracted project folder, run:

```bash
./uninstall.sh
```

The uninstaller removes the app, its GNOME shortcut, its udev rule, its module-load configuration, and its dedicated group membership. Preferences and logs are kept so they are not deleted unexpectedly. Sign out and back in after removal to refresh group membership. The `uinput` kernel module is not forcibly unloaded, because another application may be using it.

## Development and tests

Runtime dependencies are provided by the Linux distribution. To run the unit tests from the project root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
bash -n install.sh uninstall.sh scripts/check.sh
```

Or run the project check script:

```bash
./scripts/check.sh
```

The unit tests use a fake input device; they do not inject real clicks. CI checks the desktop entry, SVG icon, installer scripts, CLI behavior, a GTK window startup under a virtual display, configuration safety, and click-engine cleanup. CodeQL runs a static security analysis on the Python source. Real GUI and input-device tests still need to be carried out on a GNOME desktop; use `docs/LOCAL_TEST_PLAN.md` before calling a release stable.

Before publishing a version, follow `docs/RELEASE_CHECKLIST.md`. Maintainers can also use `docs/PUBLISHING.md` for repository setup and the first push.

## Project layout

```text
am-auto-clicker/
├── .github/                  # CI, CodeQL, Dependabot and contribution templates
├── data/                     # Desktop launcher and original SVG icon
├── docs/                     # Architecture, notices and release QA checklists
├── scripts/                  # Repeatable local validation
├── src/am_auto_clicker/
│   ├── app.py                # CLI entry point and logging
│   ├── application.py        # GTK application lifecycle
│   ├── window.py             # GTK/Libadwaita interface
│   ├── click_engine.py       # Threaded uinput click engine
│   ├── config.py             # Validated, atomic settings storage
│   └── shortcuts.py          # GNOME global-shortcut integration
├── tests/                    # Unit tests using the standard library
├── install.sh
├── uninstall.sh
├── CONTRIBUTING.md
├── LICENSE
├── SECURITY.md
└── README.md
```

## License

The project source and its original icon are released under the MIT License. See `LICENSE`. Runtime libraries are installed from the operating system and remain under their respective licenses; see `docs/THIRD_PARTY_NOTICES.md`.
