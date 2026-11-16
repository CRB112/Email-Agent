import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.agents.gmail import GmailAgent
from app.pages.login_page import LoginPage


class GmailConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "client.json"
        self.config = {"installed": {
            "client_id": "test-client", "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }}

    def write(self, config):
        self.path.write_text(json.dumps(config), encoding="utf-8")

    def test_missing_file_explains_how_to_configure_gmail(self):
        with patch("google_auth_oauthlib.flow.InstalledAppFlow.run_local_server") as browser:
            with self.assertRaisesRegex(ValueError, "Choose Gmail client JSON"):
                GmailAgent.authenticate(self.path)
        browser.assert_not_called()

    def test_invalid_client_is_rejected_before_opening_browser(self):
        cases = [
            ([], "Desktop app"),
            ({"web": self.config["installed"]}, "Desktop app"),
            ({"installed": None}, "Desktop app"),
            ({"installed": self.config["installed"], "web": {}}, "Desktop app"),
            ({"installed": {"client_id": "test-client"}}, "client_secret, auth_uri, token_uri"),
        ]
        for config, message in cases:
            with self.subTest(config=config):
                self.write(config)
                with patch("google_auth_oauthlib.flow.InstalledAppFlow.run_local_server") as browser:
                    with self.assertRaisesRegex(ValueError, message):
                        GmailAgent.authenticate(self.path)
                browser.assert_not_called()

    def test_missing_or_empty_oauth_fields_are_reported_by_name(self):
        for field in self.config["installed"]:
            for value in (None, "", "  ", 123):
                with self.subTest(field=field, value=value):
                    config = {"installed": {**self.config["installed"], field: value}}
                    self.write(config)
                    with self.assertRaisesRegex(ValueError, f"missing: {field}"):
                        GmailAgent._client_config(self.path)

    def test_malformed_json_and_encoding_have_actionable_errors(self):
        for data in (b"not json", b"\xff"):
            with self.subTest(data=data):
                self.path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "Invalid Gmail client JSON"):
                    GmailAgent._client_config(self.path)

    def test_environment_path_and_explicit_selection(self):
        self.write(self.config)
        with patch.dict(os.environ, {"GMAIL_CLIENT_SECRET_FILE": str(self.path)}):
            self.assertEqual(GmailAgent._client_config(), self.config)
        with patch.dict(os.environ, {"GMAIL_CLIENT_SECRET_FILE": "/missing/client.json"}):
            self.assertEqual(GmailAgent._client_config(self.path), self.config)

    def test_default_path_expands_home(self):
        path = self.path.parent / ".config" / "EmailSiftingAgent" / "gmail-client.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(self.config), encoding="utf-8")
        with patch.dict(os.environ, {"HOME": str(self.path.parent)}, clear=True):
            self.assertEqual(GmailAgent._client_config(), self.config)


class GmailLoginSetupTests(unittest.TestCase):
    def setUp(self):
        self.page = SimpleNamespace(
            controller=SimpleNamespace(closing=False, worker=Mock()),
            login_button=Mock(), gmail_button=Mock(), gmail_setup_button=Mock(),
            status=Mock(), gmail_credentials_file=None,
        )
        self.page.login_button.instate.return_value = False

    def test_select_client_file_and_cancel_preserves_selection(self):
        with patch("app.pages.login_page.filedialog.askopenfilename",
                   side_effect=["/tmp/selected-client.json", ""]):
            LoginPage.choose_gmail_client(self.page)
            self.assertEqual(self.page.gmail_credentials_file, "/tmp/selected-client.json")
            LoginPage.choose_gmail_client(self.page)
            self.assertEqual(self.page.gmail_credentials_file, "/tmp/selected-client.json")

    def test_cannot_change_client_during_login(self):
        self.page.login_button.instate.return_value = True
        with patch("app.pages.login_page.filedialog.askopenfilename") as choose:
            LoginPage.choose_gmail_client(self.page)
        choose.assert_not_called()

    def test_failed_login_allows_selecting_a_replacement_client(self):
        LoginPage._login_failed(self.page, ValueError("Missing auth_uri"))
        for button in (self.page.login_button, self.page.gmail_button, self.page.gmail_setup_button):
            button.config.assert_called_once_with(state="normal")
        self.assertIn("Missing auth_uri", self.page.status.config.call_args.kwargs["text"])
