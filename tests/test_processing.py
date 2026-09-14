import unittest
from unittest.mock import patch

from app.parser.ModifyCommands import Delete, Mark, Move
from app.parser.parser import parseEmailsWithJson
from tests.fakes import FakeGraph, make_email, make_rule


class ActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_targets_message(self):
        graph = FakeGraph()
        await Delete({}).modify(make_email(id="delete-me"), graph)
        self.assertEqual(graph.actions, [{"email_id": "delete-me", "action": "Delete"}])

    async def test_move_sends_destination(self):
        graph = FakeGraph()
        await Move({"Folder": "archive"}).modify(make_email(), graph)
        self.assertEqual(graph.actions, [{"email_id": "email-1", "action": "Move", "folder": "archive"}])

    async def test_mark_payloads(self):
        cases = [
            ({"Mark_type": "Read"}, {"is_read": True}),
            ({"Mark_type": "Read", "Mark_op": "Unread"}, {"is_read": False}),
            ({"Mark_type": "Importance"}, {"importance": "normal"}),
            *[({"Mark_type": "Importance", "Mark_op": value}, {"importance": value.lower()})
              for value in ("Low", "Normal", "High")],
        ]
        for settings, expected in cases:
            with self.subTest(settings=settings):
                graph = FakeGraph()
                await Mark(settings).modify(make_email(), graph)
                self.assertEqual(graph.actions, [{"email_id": "email-1", "action": "Mark", **expected}])


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def process(self, rules, emails=None, graph=None):
        graph = graph if graph is not None else FakeGraph()
        if emails is None:
            emails = [make_email(subject="Invoice due")]
        with patch("app.parser.parser.loadUserOptions", return_value={"rules": rules}):
            counts = await parseEmailsWithJson(emails, graph)
        return counts, graph.actions

    async def test_only_matching_messages_are_modified(self):
        counts, actions = await self.process([make_rule()], [
            make_email(id="bill", subject="Invoice due"),
            make_email(id="friend", subject="Lunch tomorrow?"),
        ])
        self.assertEqual(counts, (1, 1))
        self.assertEqual([action["email_id"] for action in actions], ["bill"])

    async def test_priority_and_multiple_matches(self):
        counts, actions = await self.process([
            make_rule(actions={"Mark": {"Mark_type": "Read", "Mark_op": "Unread"}}, priority=20),
            make_rule(actions={"Mark": {"Mark_type": "Read", "Mark_op": "Read"}}, priority=1),
        ])
        self.assertEqual(counts, (1, 2))
        self.assertEqual([action["is_read"] for action in actions], [True, False])

    async def test_mark_runs_before_move_even_if_configured_after_it(self):
        counts, actions = await self.process([make_rule(actions={
            "Move": {"Folder": "archive"}, "Mark": {"Mark_type": "Read"},
        })])
        self.assertEqual(counts, (1, 2))
        self.assertEqual([action["action"] for action in actions], ["Mark", "Move"])

    async def test_delete_runs_last_and_stops_later_rules(self):
        counts, actions = await self.process([
            make_rule(actions={"Delete": {}, "Mark": {"Mark_type": "Read"}}, priority=1),
            make_rule(priority=2),
        ])
        self.assertEqual(counts, (1, 2))
        self.assertEqual([action["action"] for action in actions], ["Mark", "Delete"])

    async def test_default_only_applies_to_unmatched_messages(self):
        counts, actions = await self.process([
            make_rule("match_default", {}, {"Move": {"Folder": "archive"}}, priority=0),
            make_rule(),
        ], [make_email(id="bill", subject="Invoice"), make_email(id="other")])
        self.assertEqual(counts, (2, 2))
        self.assertEqual([(a["email_id"], a["action"]) for a in actions],
                         [("bill", "Mark"), ("other", "Move")])

    async def test_default_delete_stops_other_defaults(self):
        counts, actions = await self.process([
            make_rule("match_default", {}, {"Delete": {}}, priority=0),
            make_rule("match_default", {}, priority=1),
        ])
        self.assertEqual(counts, (1, 1))
        self.assertEqual(actions[0]["action"], "Delete")

    async def test_empty_inbox_and_no_rules(self):
        self.assertEqual(await self.process([make_rule()], []), ((0, 0), []))
        self.assertEqual(await self.process([]), ((0, 0), []))

    async def test_action_failure_stops_processing(self):
        graph = FakeGraph(fail_on="Delete")
        with self.assertRaisesRegex(RuntimeError, "Simulated Delete failure"):
            await self.process([make_rule(actions={"Delete": {}, "Mark": {"Mark_type": "Read"}})], graph=graph)
        self.assertEqual([action["action"] for action in graph.actions], ["Mark"])
