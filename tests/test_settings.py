import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.parser import parser


class SettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.directory = root / "user"
        self.options_file = self.directory / "useroptions.json"
        defaults = root / "defaults.json"
        defaults.write_text('{"rules": [], "max_emails": 100}', encoding="utf-8")
        for name, value in {"USER_OPTIONS_DIR": self.directory,
                            "OPTIONS_FILE": self.options_file,
                            "DEFAULT_OPTIONS_FILE": defaults}.items():
            patcher = patch.object(parser, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_first_load_creates_defaults(self):
        self.assertEqual(parser.loadUserOptions(), {"rules": [], "max_emails": 100})
        self.assertTrue(self.options_file.exists())

    def test_saved_rules_and_checkpoint_survive_reload(self):
        options = {"rules": [], "last_sift_at": "2026-01-01T00:00:00Z",
                   "last_sift_ids": ["one", "two"], "dark_mode": True}
        parser.saveUserOptions(options)
        self.assertEqual(parser.loadUserOptions(), options)
        self.assertFalse(self.options_file.with_suffix(".tmp").exists())

    def test_loading_does_not_overwrite_existing_settings(self):
        parser.saveUserOptions({"rules": [], "max_emails": 12})
        parser.ensureUserOptions()
        self.assertEqual(parser.loadUserOptions()["max_emails"], 12)

    def test_corrupt_json_is_reported_without_overwriting_it(self):
        self.directory.mkdir()
        self.options_file.write_text("broken json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            parser.loadUserOptions()
        self.assertEqual(self.options_file.read_text(encoding="utf-8"), "broken json")

    def test_failed_replace_preserves_previous_settings(self):
        parser.saveUserOptions({"max_emails": 12})
        with patch.object(Path, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                parser.saveUserOptions({"max_emails": 30})
        self.assertEqual(parser.loadUserOptions(), {"max_emails": 12})
