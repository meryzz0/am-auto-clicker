import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from am_auto_clicker.config import ConfigStore, _normalise


class NormaliseTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(_normalise(None), {
            "interval_ms": 100, "button": "left", "limit": 0, "hotkey": "F6",
        })

    def test_values_are_clamped_to_supported_ranges(self):
        result = _normalise({
            "interval_ms": 99999, "button": "left", "limit": 999999999,
            "hotkey": "  minus  ",
        })
        self.assertEqual(result["interval_ms"], 5000)
        self.assertEqual(result["button"], "left")
        self.assertEqual(result["limit"], 10_000_000)
        self.assertEqual(result["hotkey"], "minus")

    def test_corrupted_types_do_not_crash(self):
        result = _normalise({"button": [], "interval_ms": True, "limit": "many", "hotkey": []})
        self.assertEqual(result, {
            "interval_ms": 100, "button": "left", "limit": 0, "hotkey": "F6",
        })


class ConfigStoreTests(unittest.TestCase):
    def test_atomic_persistence_and_private_file_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config_root = home / ".config"
            with (
                patch("pathlib.Path.home", return_value=home),
                patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_root)}),
            ):
                store = ConfigStore()
                store.update(interval_ms=250, button="right", limit=2500, hotkey="minus")
                loaded = json.loads((config_root / "am-auto-clicker/config.json").read_text())
                self.assertEqual(loaded["interval_ms"], 250)
                self.assertEqual(loaded["button"], "right")
                self.assertEqual(loaded["limit"], 2500)
                self.assertEqual(loaded["hotkey"], "minus")
                mode = (config_root / "am-auto-clicker/config.json").stat().st_mode & 0o777
                self.assertEqual(mode, 0o600)

    def test_failed_save_does_not_change_in_memory_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch("pathlib.Path.home", return_value=home), patch.dict(
                os.environ, {"XDG_CONFIG_HOME": str(home / ".config")},
            ):
                store = ConfigStore()
                before = store.data
                with patch.object(store, "save", side_effect=OSError("disk is read-only")):
                    with self.assertRaises(OSError):
                        store.update(interval_ms=250)
                self.assertEqual(store.data, before)



if __name__ == "__main__":
    unittest.main()
