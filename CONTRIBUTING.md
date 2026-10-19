# Contributing

Thanks for taking an interest in AM Auto Clicker. Small, focused changes are easier to review than broad rewrites.

## Before opening a pull request

1. Open an issue for significant behavior changes so the proposed direction can be discussed first.
2. Keep changes scoped to one problem and explain the user-visible effect.
3. Do not bundle compiled artifacts, virtual environments, logs, personal configuration, or generated build folders.
4. Do not add copied code, screenshots, icons, fonts, or other assets unless their license permits redistribution and the required attribution is included.
5. Run `./scripts/check.sh` and include manual test details for any change involving GTK, GNOME shortcuts, udev, or input events.

## Development requirements

Use a supported Ubuntu-based GNOME environment with the system packages listed in the README. The project intentionally uses the distribution's Python/GI stack rather than a private virtual environment for GTK bindings.

## Pull requests

Describe the problem, the approach, and how you tested it. If a change affects device permissions or the installer, state exactly which system files or groups it modifies. Avoid promising compatibility with a specific game or runtime unless it was tested there.
