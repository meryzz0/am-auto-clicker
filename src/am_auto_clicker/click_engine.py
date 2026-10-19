"""Threaded uinput click engine with bounded settings and guaranteed button release."""
from __future__ import annotations

import errno
import threading
import time
from collections.abc import Callable
from typing import Any

BUTTON_CODES = {"left": "BTN_LEFT", "right": "BTN_RIGHT", "middle": "BTN_MIDDLE"}


class ClickEngine:
    """Generate mouse clicks through Linux uinput without running the UI as root."""

    def __init__(self, emit: Callable[[str, Any], None]) -> None:
        self._emit = emit
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self, interval_ms: int, button: str, limit: int) -> None:
        if button not in BUTTON_CODES:
            raise ValueError("Choose a valid mouse button.")
        if not 10 <= interval_ms <= 5000:
            raise ValueError("The interval must be between 10 and 5000 milliseconds.")
        if not 0 <= limit <= 10_000_000:
            raise ValueError("The click limit must be between 0 and 10,000,000.")

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("The clicker is already running.")
            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                args=(interval_ms, button, limit, self._stop_event),
                name="am-auto-clicker-engine",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def stop_and_wait(self, timeout: float = 1.0) -> None:
        self.stop()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))

    def _run(self, interval_ms: int, button: str, limit: int, stop_event: threading.Event) -> None:
        device = None
        button_pressed = False
        clicks = 0
        failure: Exception | None = None
        button_name = BUTTON_CODES[button]

        try:
            from evdev import UInput, ecodes

            capabilities = {
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
                # Relative axes help compositors and SDL identify the virtual device as a mouse.
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
            }
            device = UInput(capabilities, name="AM Auto Clicker")
            button_code = getattr(ecodes, button_name)
            self._emit("started", None)
            # Give the UI time to minimize before the first synthetic click lands.
            if stop_event.wait(0.20):
                return

            interval_s = interval_ms / 1000.0
            press_s = min(0.004, interval_s * 0.35)
            next_deadline = time.monotonic()
            last_update = time.monotonic()

            while not stop_event.is_set():
                device.write(ecodes.EV_KEY, button_code, 1)
                device.syn()
                button_pressed = True

                if stop_event.wait(press_s):
                    break

                device.write(ecodes.EV_KEY, button_code, 0)
                device.syn()
                button_pressed = False
                clicks += 1

                now = time.monotonic()
                if clicks % 5 == 0 or now - last_update >= 0.15 or (limit and clicks >= limit):
                    self._emit("count", clicks)
                    last_update = now

                if limit and clicks >= limit:
                    break

                next_deadline += interval_s
                remaining = next_deadline - time.monotonic()
                if remaining > 0:
                    if stop_event.wait(remaining):
                        break
                else:
                    # Do not run catch-up bursts after a scheduling delay.
                    next_deadline = time.monotonic()

        except Exception as exc:  # the UI turns this into a useful error message
            failure = exc
        finally:
            if device is not None:
                try:
                    from evdev import ecodes
                    if button_pressed:
                        device.write(ecodes.EV_KEY, getattr(ecodes, button_name), 0)
                        device.syn()
                    else:
                        # A final release is deliberately idempotent.
                        device.write(ecodes.EV_KEY, getattr(ecodes, button_name), 0)
                        device.syn()
                except Exception as release_error:
                    if failure is None:
                        failure = release_error
                try:
                    device.close()
                except Exception as close_error:
                    if failure is None:
                        failure = close_error

            self._emit("finished", {"clicks": clicks, "error": failure})


def error_message(error: Exception) -> str:
    """Map common system-level failures to practical next steps."""
    if isinstance(error, PermissionError) or getattr(error, "errno", None) in {
        errno.EACCES, errno.EPERM
    }:
        return (
            "AM Auto Clicker cannot access /dev/uinput. Run install.sh from the extracted "
            "project folder, "
            "then sign out of Zorin and sign back in so the new device permission takes effect. "
            "Do not run the app with sudo."
        )
    if isinstance(error, FileNotFoundError) or getattr(error, "errno", None) == errno.ENOENT:
        return (
            "The Linux uinput device or python-evdev package is missing. Run install.sh again, "
            "then sign out and back in."
        )
    if type(error).__name__ == "ModuleNotFoundError" and "evdev" in str(error):
        return (
            "The python-evdev dependency is missing. Run install.sh again to install "
            "the required packages."
        )
    detail = str(error).strip() or type(error).__name__
    return f"The click engine encountered an error: {detail}"
