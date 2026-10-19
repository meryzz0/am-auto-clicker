# Publishing on GitHub

This checklist is for the maintainer publishing the source project. The first public version is an early preview; do not create a stable release until the real desktop test plan has been completed.

## Repository setup

Create an empty public repository on the `meryzz0` account with these details:

- **Repository name:** `am-auto-clicker`
- **Description:** `A lightweight autoclicker for GNOME desktops on Linux, built with GTK 4, Libadwaita, and uinput.`
- **Topics:** `linux`, `ubuntu`, `zorin-os`, `gnome`, `wayland`, `gtk4`, `libadwaita`, `autoclicker`, `python`, `uinput`
- **Visibility:** Public

Do not initialize the repository with a README, license, or `.gitignore`; this source archive already contains them.

## Initial push

Extract the project archive, open a terminal in the extracted `am-auto-clicker` directory, and review the complete file list before committing. Then run:

```bash
git init -b main
git add .
git diff --cached --check
git status --short
```

Review the output of `git status --short`. It should contain only the project files. Do not proceed if it shows personal configuration, logs, tokens, private keys, build artefacts, or unrelated files. Then create and push the first commit:

```bash
git commit -m "Prepare AM Auto Clicker 0.1.0 preview"
git remote add origin https://github.com/meryzz0/am-auto-clicker.git
git push -u origin main
```

If Git asks for your identity, set your Git author name and an email associated with your GitHub account. Authenticate through Git Credential Manager, the GitHub CLI, or the browser prompt; never paste an access token into a public issue or source file.

If the repository already exists or `origin` is configured, inspect `git remote -v` first and do not overwrite the existing remote.

## After pushing

1. Open the repository's **Actions** tab and wait for CI and CodeQL to finish. Fix failures before advertising the build.
2. Run every applicable item in `LOCAL_TEST_PLAN.md` on a real Ubuntu-based GNOME desktop. The CI virtual-display smoke test does not prove that a physical `uinput` device works or that target apps accept its events.
3. In **Settings → Security**, enable Dependabot alerts, secret scanning and push protection where available, and private vulnerability reporting if available.
4. Verify the repository license shown by GitHub is MIT and that the README, security policy, contribution guide, and code of conduct display correctly.
5. Keep the version marked as an early preview until manual testing is complete. Then follow `RELEASE_CHECKLIST.md` before creating any release tag.

## Copyright and third-party code

Before each release, check the origin and license of every source file, icon, screenshot, and bundled asset. Keep the upstream attribution and license text for any third-party material, and update `THIRD_PARTY_NOTICES.md`. The current project does not bundle its runtime libraries; they are installed from the distribution repositories. The MIT notice identifies `meryzz0` as the declared copyright holder for this project's original source and icon. This checklist is not legal advice.
