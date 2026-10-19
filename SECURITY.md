# Security Policy

## Supported version

Security fixes are intended for the latest code on the `main` branch. Early preview versions may contain defects and should not be treated as security-audited software.

## Reporting a vulnerability

Please do not publish exploit details or sensitive system information in a public issue. If GitHub's **Report a vulnerability** feature is available for this repository, use it. Otherwise, open a minimal issue asking for a private reporting channel without including the exploit details.

## Security design notes

- The application itself does not run as root and does not make network requests.
- The installer uses `sudo` for APT packages, a dedicated `am-auto-clicker-input` group, the `uinput` kernel module, and a udev rule for `/dev/uinput`.
- Members of the dedicated group can create virtual input events. Grant membership only to trusted local users.
- The application writes preferences and logs under XDG user directories. It does not store credentials.
- Input events are sent to the system's input stack. The app cannot guarantee that every target app or game accepts those events.
