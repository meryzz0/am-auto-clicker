"""GTK application lifecycle and command-line routing."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from . import APP_ID
from .window import MainWindowController


class AMAutoClicker(Adw.Application):
    """Single-instance GTK application that delegates UI behavior to the window controller."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.controller: MainWindowController | None = None
        self.connect("command-line", self._on_command_line)
        self.connect("shutdown", self._on_shutdown)

    def _on_command_line(
        self, _app: Gio.Application, command_line: Gio.ApplicationCommandLine
    ) -> int:
        args = command_line.get_arguments()[1:]
        controller = self.controller

        if "--quit" in args:
            if controller is None:
                self.quit()
            else:
                controller.request_quit()
            return 0

        was_open = controller is not None and controller.is_open
        if controller is None:
            controller = MainWindowController(self)
            self.controller = controller

        if "--toggle" in args:
            if was_open:
                controller.toggle()
            else:
                controller.show()
                controller._set_status(
                    "ready",
                    "The app is ready. Use your global shortcut to start clicking "
                    "while the target app is focused.",
                )
        else:
            controller.show()
        return 0

    def _on_shutdown(self, *_args: object) -> None:
        if self.controller is not None:
            self.controller.shutdown()
