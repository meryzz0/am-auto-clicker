# Local integration test plan

The unit tests use a fake input device. Before describing a release as stable, run this plan on a supported Ubuntu-based GNOME desktop. Record the distribution, version, session type, app version, and actual result for every test.

## Basic launch and settings

- [ ] Install using `./install.sh` from a regular user account and confirm the consent prompt accurately describes the changes.
- [ ] Sign out and sign back in, then launch AM Auto Clicker from the application menu.
- [ ] Confirm the app reports whether `/dev/uinput` is available and does not require launching the app with `sudo`.
- [ ] Change the interval, button, click limit, and global shortcut; close and reopen the app and confirm saved settings persist.
- [ ] Test a punctuation shortcut and a modifier combination. Verify the installer-owned shortcut is the only binding changed.

## Input lifecycle

- [ ] Use a harmless desktop target to verify a left click, right click, and middle click.
- [ ] Start clicking and press the same shortcut to stop. Confirm the cursor does not remain in a pressed-button state.
- [ ] Set a short click limit and verify the exact number is reached before the worker stops.
- [ ] Stop immediately during the startup delay and confirm no click is emitted.
- [ ] Close the app while clicking and confirm the worker stops and releases the button.
- [ ] Test at the minimum interval, a typical interval, and the maximum interval; confirm the UI remains responsive.
- [ ] Test the intended target application separately. Some games, emulators, remote desktops, and sandboxed applications may ignore synthetic input.

## Removal and recovery

- [ ] Run `./uninstall.sh` and confirm only the AM Auto Clicker shortcut, launcher, icon, app files, udev rule, module-load file, and dedicated group membership are removed.
- [ ] Confirm preferences and logs remain, as documented.
- [ ] Sign out and back in. Verify unrelated GNOME shortcuts remain unchanged.

Do not mark an item as passed unless it was actually tested on the named machine. Attach only redacted logs to an issue.
