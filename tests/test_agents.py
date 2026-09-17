import base64
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.agents.base import EmailAgent, next_checkpoint
from app.agents.gmail import GmailAgent
from app.agents.microsoft import MicrosoftGraphAgent
from app.pages.login_page import LoginPage
from app.services.control import SiftCancelled
from app.services.sifting import sift
from tests.fakes import FakeGraph, make_email, make_rule


def record(message_id, milliseconds=1000):
    raw = b'From: Person <person@example.com>\r\nSubject: Invoice\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nPayment due'
    return {"id": message_id, "internalDate": str(milliseconds),
            "raw": base64.urlsafe_b64encode(raw).decode().rstrip("=")}


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Mock()
        self.messages = self.client.users.return_value.messages.return_value
        self.agent = GmailAgent(self.client)

    def inbox(self, records):
        self.messages.list.return_value.execute.side_effect = None
        self.messages.list.return_value.execute.return_value = {
            "messages": [{"id": r["id"]} for r in records]}
        lookup = {r["id"]: r for r in records}
        self.messages.get.side_effect = lambda **kw: Mock(execute=Mock(return_value=lookup[kw["id"]]))

    def test_base_requires_implementation(self):
        with self.assertRaises(TypeError):
            EmailAgent()
        self.assertIsInstance(self.agent, EmailAgent)
        self.assertIsInstance(MicrosoftGraphAgent(FakeGraph()), EmailAgent)

    async def test_microsoft_move_updates_id_for_later_actions(self):
        graph = FakeGraph()
        agent = MicrosoftGraphAgent(graph)
        email = make_email()
        await agent.move(email, "archive")
        await agent.delete(email)
        self.assertEqual(graph.actions[-1]["email_id"], "moved-email-1")

    async def test_gmail_decodes_and_sorts_all_pages_before_limit(self):
        self.inbox([record("new", 3000), record("old", 1000)])
        self.messages.list.return_value.execute.side_effect = [
            {"messages": [{"id": "new"}], "nextPageToken": "page2"},
            {"messages": [{"id": "old"}]},
        ]
        emails = await self.agent.get_emails(max_emails=1, oldest_first=True)
        self.assertEqual([e.id for e in emails], ["old"])
        self.assertEqual(emails[0].from_.email_address.address, "person@example.com")
        self.assertEqual(emails[0].subject, "Invoice")
        self.assertEqual(emails[0].body.content, "Payment due")
        self.assertEqual(self.messages.list.call_args.kwargs["pageToken"], "page2")

    async def test_gmail_checkpoint_ties_and_upper_boundary(self):
        self.inbox([record("a"), record("b"), record("c"), record("future", 2000)])
        at, ids = "1970-01-01T00:00:01Z", []
        done = []
        for _ in range(3):
            emails = await self.agent.get_emails(at, 1, oldest_first=True,
                checkpoint_ids=ids, received_before="1970-01-01T00:00:01.500Z")
            done.extend(e.id for e in emails)
            at, ids = next_checkpoint(emails, at, ids, "1970-01-01T00:00:01.500Z")
        self.assertEqual(done, ["a", "b", "c"])
        self.assertEqual(ids, ["a", "b", "c"])
        emails = await self.agent.get_emails(at, oldest_first=False)
        self.assertEqual([e.id for e in emails], ["future"])

    async def test_cancellation_after_list_stops_message_fetch(self):
        cancel = Event()
        def response():
            cancel.set()
            return {"messages": [{"id": "a"}]}
        self.messages.list.return_value.execute.side_effect = response
        with self.assertRaises(SiftCancelled):
            await self.agent.get_emails(cancel=cancel)
        self.messages.get.assert_not_called()

    async def test_mark_label_mapping(self):
        for kind, value, added, removed in [
            ("Read", "Read", [], ["UNREAD"]),
            ("Read", "Unread", ["UNREAD"], []),
            ("Importance", "High", ["IMPORTANT"], []),
            ("Importance", "Normal", [], ["IMPORTANT"]),
            ("Importance", "Low", [], ["IMPORTANT"]),
        ]:
            await self.agent.mark(make_email(), kind, value)
            self.assertEqual(self.messages.modify.call_args.kwargs["body"],
                             {"addLabelIds": added, "removeLabelIds": removed})

    async def test_move_label_archive_and_missing_destination(self):
        self.client.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": [{"id": "Label_1", "name": "Receipts", "type": "user"}]}
        for destination in ("Receipts", "Label_1"):
            await self.agent.move(make_email(), destination)
            self.assertEqual(self.messages.modify.call_args.kwargs["body"],
                             {"addLabelIds": ["Label_1"], "removeLabelIds": ["INBOX"]})
        await self.agent.move(make_email(), "archive")
        self.assertEqual(self.messages.modify.call_args.kwargs["body"],
                         {"addLabelIds": [], "removeLabelIds": ["INBOX"]})
        with self.assertRaises(ValueError):
            await self.agent.move(make_email(), "missing")

    async def test_gmail_sifts_through_shared_engine(self):
        self.inbox([record("a")])
        result = await sift(self.agent, {"rules": [make_rule(actions={"Delete": {}})]},
                            "since_last", Event(), Mock())
        self.assertEqual((result.examined, result.modified, result.modifications), (1, 1, 1))
        self.messages.trash.assert_called_once_with(userId="me", id="a")

    async def test_failure_propagates_without_checkpoint(self):
        self.inbox([record("a")])
        self.messages.modify.return_value.execute.side_effect = RuntimeError("offline")
        with self.assertRaisesRegex(RuntimeError, "offline"):
            await sift(self.agent, {"rules": [make_rule()]}, "since_last", Event(), Mock())

    async def test_invalid_limit_makes_no_requests(self):
        with self.assertRaises(ValueError):
            await self.agent.get_emails(max_emails=0)
        self.client.users.assert_not_called()

    def test_logout_closes_session(self):
        self.agent.logout()
        self.client.close.assert_called_once()
        self.assertIsNone(self.agent.client)

    def test_gmail_login_runs_on_worker(self):
        page = SimpleNamespace(controller=SimpleNamespace(closing=False, worker=Mock()),
            login_button=Mock(), gmail_button=Mock(), status=Mock(),
            _logged_in=Mock(), _login_failed=Mock())
        page.login_button.instate.return_value = False
        with patch.object(GmailAgent, "authenticate") as authenticate:
            LoginPage.login_gmail(page)
            authenticate.assert_not_called()
            page.controller.worker.submit.call_args.args[0](Mock())
            authenticate.assert_called_once()

    def test_login_clears_checkpoint_but_preserves_rules(self):
        page = SimpleNamespace(provider="gmail", login_button=Mock(), gmail_button=Mock(),
                               controller=Mock(), _login_failed=Mock())
        options = {"rules": ["saved"], "last_sift_at": "old", "last_sift_ids": ["old-id"]}
        with patch("app.pages.login_page.loadUserOptions", return_value=options), \
             patch("app.pages.login_page.saveUserOptions") as save:
            LoginPage._logged_in(page, self.agent)
        self.assertEqual(save.call_args.args[0], {"rules": ["saved"], "provider": "gmail", "mailbox_key": None})
        self.assertIs(page.controller.email_agent, self.agent)

    def test_same_account_preserves_checkpoint(self):
        self.agent.mailbox_key = "gmail:person@example.com"
        options = {"mailbox_key": self.agent.mailbox_key, "last_sift_at": "old", "last_sift_ids": ["a"]}
        page = SimpleNamespace(provider="gmail", login_button=Mock(), gmail_button=Mock(),
                               controller=Mock(), _login_failed=Mock())
        with patch("app.pages.login_page.loadUserOptions", return_value=options), \
             patch("app.pages.login_page.saveUserOptions") as save:
            LoginPage._logged_in(page, self.agent)
        self.assertEqual(save.call_args.args[0]["last_sift_at"], "old")
        self.assertEqual(save.call_args.args[0]["last_sift_ids"], ["a"])

    def test_gmail_authentication_uses_desktop_flow_and_account_identity(self):
        with patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file") as flow, \
             patch("googleapiclient.discovery.build", return_value=self.client) as build:
            self.client.users.return_value.getProfile.return_value.execute.return_value = {
                "emailAddress": "Person@gmail.com"}
            agent = GmailAgent.authenticate("/tmp/client.json")
        self.assertEqual(agent.mailbox_key, "gmail:person@gmail.com")
        flow.assert_called_once_with("/tmp/client.json", ["https://www.googleapis.com/auth/gmail.modify"])
        flow.return_value.run_local_server.assert_called_once_with(port=0)
        build.assert_called_once_with("gmail", "v1",
            credentials=flow.return_value.run_local_server.return_value, cache_discovery=False)
