"""Lightweight checks for release metadata and bundled assets."""
from __future__ import annotations

import configparser
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrityTests(unittest.TestCase):
    def test_project_and_runtime_versions_match(self):
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        runtime = (ROOT / "src/am_auto_clicker/__init__.py").read_text(encoding="utf-8")
        project_version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', metadata)
        runtime_version = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', runtime)
        self.assertIsNotNone(project_version)
        self.assertIsNotNone(runtime_version)
        self.assertEqual(project_version.group(1), runtime_version.group(1))

    def test_packaging_uses_modern_license_metadata(self):
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(metadata, r'(?m)^license\s*=\s*"MIT"\s*$')
        self.assertNotIn("License :: OSI Approved :: MIT License", metadata)

    def test_desktop_entry_has_expected_identity_and_command(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ROOT / "data/com.am.autoclicker.desktop", encoding="utf-8")
        self.assertTrue(parser.has_section("Desktop Entry"))
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Name"], "AM Auto Clicker")
        self.assertEqual(entry["Exec"], "am-auto-clicker --show")
        self.assertEqual(entry["Icon"], "com.am.autoclicker")

    def test_icon_is_standalone_svg_without_active_or_remote_content(self):
        root = ET.parse(ROOT / "data/com.am.autoclicker.svg").getroot()
        forbidden_tags = {"script", "foreignObject"}
        for element in root.iter():
            self.assertNotIn(element.tag.rsplit("}", 1)[-1], forbidden_tags)
            for key, value in element.attrib.items():
                if key.rsplit("}", 1)[-1] in {"href", "src"}:
                    self.assertFalse(value.startswith(("http://", "https://", "file://")))

    def test_installer_does_not_reference_prototype_components(self):
        for name in ("install.sh", "uninstall.sh"):
            content = (ROOT / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("mockclicker", content)
            self.assertNotIn("wayclicker", content)
            self.assertNotIn("blur-auto-clicker", content)

    def test_installer_refuses_to_overwrite_unrecognised_system_files(self):
        content = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn(
            "Never overwrite a pre-existing system configuration that is not ours", content
        )
        self.assertIn("current\" != \"$expected\"", content)
        self.assertIn("Refusing to overwrite an existing system file", content)

    def test_uninstaller_checks_managed_file_contents_before_removal(self):
        content = (ROOT / "uninstall.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ "$current" == "$expected" ]]', content)
        self.assertIn("Leaving %s unchanged", content)

    def test_application_does_not_invoke_shell_for_subprocesses(self):
        for path in (ROOT / "src/am_auto_clicker").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", content, path.name)


if __name__ == "__main__":
    unittest.main()
