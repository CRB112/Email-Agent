import unittest

from tests.fakes import make_rule
from tests.simulate import simulate


class SimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_modified_and_unchanged_emails(self):
        result = await simulate({"rules": [make_rule(actions={"Delete": {}})]}, [
            {"id": "bill", "subject": "Invoice"},
            {"id": "friend", "subject": "Hello"},
        ])
        self.assertEqual(result, {
            "emails_supplied": 2, "emails_modified": 1, "modifications": 1,
            "actions": [{"email_id": "bill", "action": "Delete"}],
            "unchanged_email_ids": ["friend"],
        })

    async def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique id"):
            await simulate({"rules": []}, [{"id": "same"}, {"id": "same"}])
