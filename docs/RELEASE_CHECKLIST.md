# Release checklist

- [ ] Run `./scripts/check.sh` from a clean checkout.
- [ ] Review the CI GTK-startup smoke test and CodeQL results; neither replaces manual desktop and device testing.
- [ ] Run the desktop-entry and SVG validators used by CI.
- [ ] Complete `docs/LOCAL_TEST_PLAN.md` on at least one supported Ubuntu-based GNOME desktop.
- [ ] Review `git diff --check` and `git status`; exclude caches, build outputs, personal configuration, logs, and local secrets.
- [ ] Check all bundled code and assets for origin, license, attribution, and redistribution permission.
- [ ] Verify the version in `pyproject.toml` and `src/am_auto_clicker/__init__.py` matches the release tag.
- [ ] Update `CHANGELOG.md` with user-visible changes and known limitations.
- [ ] Wait for CI and CodeQL to complete after pushing to `main`.
- [ ] In repository settings, enable Dependabot alerts, secret scanning and push protection where available; enable private vulnerability reporting if available.
- [ ] Create a Git tag and GitHub Release only after manual integration tests pass.
- [ ] Publish source archives with release notes; do not upload a binary package unless it has been built and tested from this source revision.
