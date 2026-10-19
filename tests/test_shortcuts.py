import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from am_auto_clicker.shortcuts import _gvariant_string, format_binding, set_global_binding


class ShortcutFormattingTests(unittest.TestCase):
    def test_punctuation_key(self):
        self.assertEqual(format_binding("minus"), "-")

    def test_control_combination(self):
        self.assertEqual(format_binding("<Control>F6"), "Ctrl + F6")

    def test_multiple_modifiers(self):
        self.assertEqual(format_binding("<Alt><Shift>z"), "Alt + Shift + Z")

    def test_gvariant_quoting(self):
        self.assertEqual(_gvariant_string("a'b\\c"), "'a\\'b\\\\c'")

    def test_set_binding_refuses_a_path_outside_its_namespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config" / "am-auto-clicker"
            config.mkdir(parents=True)
            (config / "keybinding-path").write_text("/org/gnome/other-app/", encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(Path(temporary) / "config")}):
                with self.assertRaisesRegex(RuntimeError, "path is invalid"):
                    set_global_binding("minus")

    def test_set_binding_only_updates_its_own_shortcut(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config" / "am-auto-clicker"
            config.mkdir(parents=True)
            path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom4/"
            (config / "keybinding-path").write_text(path, encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(Path(temporary) / "config")}), \
                 patch("am_auto_clicker.shortcuts._run_gsettings") as run:
                run.side_effect = [
                    "'AM Auto Clicker: Toggle'",
                    "'/home/test/.local/bin/am-auto-clicker --toggle'",
                    "",
                ]
                with patch("pathlib.Path.home", return_value=Path("/home/test")):
                    set_global_binding("minus")
                self.assertEqual(run.call_count, 3)
                expected_schema = (
                    "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:" + path
                )
                self.assertEqual(run.call_args_list[-1].args[0][0:2], ["set", expected_schema])

    def test_set_binding_refuses_a_shortcut_owned_by_another_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config" / "am-auto-clicker"
            config.mkdir(parents=True)
            path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/"
            (config / "keybinding-path").write_text(path, encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(Path(temporary) / "config")}), \
                 patch(
                     "am_auto_clicker.shortcuts._run_gsettings",
                     side_effect=["'Other app'", "'/usr/bin/other-app' "],
                 ):
                with self.assertRaisesRegex(RuntimeError, "does not belong"):
                    set_global_binding("minus")


if __name__ == "__main__":
    unittest.main()
