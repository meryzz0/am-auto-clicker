"""CLI smoke tests that intentionally run without a display or GTK import."""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from am_auto_clicker import APP_NAME, __version__
from am_auto_clicker.app import main


class CliTests(unittest.TestCase):
    def test_version_does_not_start_the_gui(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["am-auto-clicker", "--version"]), redirect_stdout(output):
            result = main()
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), f"{APP_NAME} {__version__}")

    def test_help_describes_supported_commands(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["am-auto-clicker", "--help"]), redirect_stdout(output):
            result = main()
        self.assertEqual(result, 0)
        self.assertIn("--show|--toggle|--quit|--version", output.getvalue())


if __name__ == "__main__":
    unittest.main()
