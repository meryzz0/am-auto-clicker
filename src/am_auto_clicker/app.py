"""CLI entry point; version/help work without importing GTK."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import APP_NAME, __version__


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args:
        print(f"{APP_NAME} {__version__}")
        return 0
    if "--help" in args:
        print("Usage: am-auto-clicker [--show|--toggle|--quit|--version]")
        return 0

    state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    ) / "am-auto-clicker"
    try:
        state_home.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(state_home, 0o700)
        file_handler = RotatingFileHandler(
            state_home / "am-auto-clicker.log",
            maxBytes=256_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logging.basicConfig(level=logging.INFO, handlers=[file_handler], force=True)
    except OSError:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Import the GTK application only when a GUI session is requested.
    from .application import AMAutoClicker

    app = AMAutoClicker()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        if app.controller is not None:
            app.controller.engine.stop_and_wait(0.8)
        return 130
