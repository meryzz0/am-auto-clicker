# Changelog

Notable changes are recorded here. Versions before the first public repository snapshot were development iterations and are not separately published.

## 0.1.0 — 2026-10-19

- Prepared the first public source preview.
- Separated the CLI, single-instance GTK application, UI controller, configuration store, global-shortcut integration, and click engine into focused modules.
- Generalized in-app wording so the project is not tied to one game or Android runtime.
- Removed prototype-specific cleanup and migration from the public installer.
- Added explicit installation consent, XDG data directory support, and safer shortcut ownership checks.
- Added repository policies, third-party notices, automated checks, and issue templates.
- Added tests for validated settings, global-shortcut ownership, CLI smoke behavior, and virtual input lifecycle.
- Added CI checks with read-only repository permissions and no persisted checkout credentials.

This is a preview release. It has not yet been validated on a matrix of real desktop environments or target applications.
