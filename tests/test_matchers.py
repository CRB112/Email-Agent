import unittest

from app.parser.MatchCommands import COMMAND_CLASSES
from tests.fakes import make_email


class MatcherTests(unittest.TestCase):
    def test_exact_matchers(self):
        cases = [
            ("match_subject", {"Sub": "Invoice"}, True),
            ("match_subject", {"Sub": "invoice"}, False),
            ("match_sender", {"Sender": " BILLING@EXAMPLE.COM "}, True),
            ("match_sender", {"Sender": "other@example.com"}, False),
            ("match_domain", {"Domain": " EXAMPLE.COM "}, True),
            ("match_domain", {"Domain": "ample.com"}, False),
            ("match_default", {}, True),
        ]
        email = make_email(subject="Invoice", sender="billing@example.com")
        for name, settings, expected in cases:
            with self.subTest(matcher=name, settings=settings):
                self.assertEqual(COMMAND_CLASSES[name](settings).testMatch(email), expected)

    def test_contains_searches_the_correct_field(self):
        email = make_email(subject="SubjectToken", sender="SenderToken@DomainToken.com", body="BodyToken")
        for name, word in [
            ("match_body", "BodyToken"),
            ("match_body_contains", "BodyToken"),
            ("match_subject_contains", "SubjectToken"),
            ("match_sender_contains", "SenderToken"),
            ("match_domain_contains", "DomainToken"),
        ]:
            with self.subTest(matcher=name):
                self.assertTrue(COMMAND_CLASSES[name]({"Words": [word]}).testMatch(email))
                self.assertFalse(COMMAND_CLASSES[name]({"Words": ["missing"]}).testMatch(email))
        self.assertFalse(COMMAND_CLASSES["match_domain_contains"](
            {"Words": ["SenderToken"]}).testMatch(email))

    def test_any_all_and_case_sensitivity(self):
        for mode, words, sensitive, expected in [
            ("Any", ["invoice", "missing"], False, True),
            ("All", ["invoice", "missing"], False, False),
            ("All", ["invoice", "due"], False, True),
            ("Any", ["invoice"], True, False),
            ("Any", ["Invoice"], True, True),
            ("Any", [], False, False),
        ]:
            with self.subTest(mode=mode, words=words, sensitive=sensitive):
                matcher = COMMAND_CLASSES["match_subject_contains"](
                    {"Words": words, "Type": mode, "CaseSensitive": sensitive})
                self.assertEqual(matcher.testMatch(make_email(subject="Invoice due")), expected)

    def test_unicode_casefold(self):
        matcher = COMMAND_CLASSES["match_subject_contains"]({"Words": ["STRASSE"]})
        self.assertTrue(matcher.testMatch(make_email(subject="Straße")))

    def test_contains_handles_missing_fields(self):
        email = make_email(subject=None)
        email.body = None
        email.from_ = None
        for name in ("match_body_contains", "match_subject_contains",
                     "match_sender_contains", "match_domain_contains"):
            with self.subTest(matcher=name):
                self.assertFalse(COMMAND_CLASSES[name]({"Words": ["invoice"]}).testMatch(email))

    def test_malformed_domain_does_not_match(self):
        for name, settings in [("match_domain", {"Domain": "example.com"}),
                               ("match_domain_contains", {"Words": ["example"]})]:
            with self.subTest(matcher=name):
                self.assertFalse(COMMAND_CLASSES[name](settings).testMatch(make_email(sender="invalid")))

    def test_invalid_match_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            COMMAND_CLASSES["match_body_contains"]({"Words": ["invoice"], "Type": "Neither"})
