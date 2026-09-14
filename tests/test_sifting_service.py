import asyncio
from threading import Event, get_ident
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.pages.main_page import MainPage
from app.pages.login_page import LoginPage
from app.microsoftGraph.email import getEmails
from app.services.control import SiftCancelled
from app.services.sifting import sift, SiftResult
from app.services.worker import BackgroundWorker
from tests.fakes import FakeGraph, make_email, make_rule


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def run_sift(self, mode="since_last", cancel=None, report=None, graph=None):
        options = {"rules": [make_rule()], "last_sift_at": "2025-01-01T00:00:00Z",
                   "last_sift_ids": ["old"]}
        emails = [make_email(id="one", subject="Invoice"), make_email(id="two")]
        with patch("app.services.sifting.getEmails", AsyncMock(return_value=emails)):
            return await sift(graph or FakeGraph(), options, mode, cancel or Event(), report or Mock())

    async def test_success_reports_examined_and_modified_separately(self):
        progress = Mock()
        result = await self.run_sift(report=progress)
        self.assertEqual((result.examined, result.modified, result.modifications), (2, 1, 1))
        self.assertEqual(result.settings_update["last_sift_ids"], ["one", "two"])
        self.assertEqual(progress.call_args.args, ("Sifting emails...", 2, 2))

    async def test_full_sift_does_not_update_checkpoint(self):
        result = await self.run_sift(mode="all")
        self.assertEqual(result.settings_update, {"sift_mode": "all"})

    async def test_cancel_before_fetch_does_no_work(self):
        cancel = Event()
        cancel.set()
        with patch("app.services.sifting.getEmails", AsyncMock()) as fetch:
            with self.assertRaises(SiftCancelled):
                await sift(FakeGraph(), {}, "all", cancel, Mock())
            fetch.assert_not_awaited()

    async def test_fetch_cancellation_stops_before_next_page(self):
        cancel = Event()
        builder = Mock()
        async def first_page(**kwargs):
            cancel.set()
            return SimpleNamespace(value=[], odata_next_link="next-page")
        builder.get = AsyncMock(side_effect=first_page)
        graph = Mock()
        graph.me.mail_folders.by_mail_folder_id.return_value.messages = builder
        with self.assertRaises(SiftCancelled):
            await getEmails(graph, cancel=cancel)
        builder.with_url.assert_not_called()

    async def test_cancel_between_messages_preserves_completed_actions(self):
        cancel = Event()
        graph = FakeGraph()
        def report(text, done, total):
            if done == 1:
                cancel.set()
        with self.assertRaises(SiftCancelled):
            await self.run_sift(cancel=cancel, report=report, graph=graph)
        self.assertEqual(len(graph.actions), 1)

    async def test_failure_returns_no_checkpoint(self):
        with self.assertRaisesRegex(RuntimeError, "Simulated Mark failure"):
            await self.run_sift(graph=FakeGraph(fail_on="Mark"))

    async def test_cancel_finishes_all_actions_for_current_message(self):
        cancel = Event()
        graph = FakeGraph()
        original = graph.record
        def record(*args, **kwargs):
            original(*args, **kwargs)
            cancel.set()
        graph.record = record
        options = {"rules": [make_rule(actions={"Mark": {"Mark_type": "Read"}, "Delete": {}})]}
        emails = [make_email(id="one", subject="Invoice"), make_email(id="two", subject="Invoice")]
        with patch("app.services.sifting.getEmails", AsyncMock(return_value=emails)):
            with self.assertRaises(SiftCancelled):
                await sift(graph, options, "all", cancel, Mock())
        self.assertEqual([a["action"] for a in graph.actions], ["Mark", "Delete"])


class WorkerTests(unittest.TestCase):
    def test_work_is_off_thread_and_callbacks_wait_for_drain(self):
        worker = BackgroundWorker()
        release = Event()
        entered = Event()
        seen = []
        main_thread = get_ident()
        def operation(report):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test timed out")
            report(get_ident())
            return get_ident()
        worker.submit(operation, lambda result: seen.append(("result", get_ident(), result)),
                      lambda error: seen.append(("error", error)),
                      lambda thread: seen.append(("progress", get_ident(), thread)))
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(seen, [])
        finally:
            release.set()
            worker.close()
            worker.thread.join(3)
        self.assertFalse(worker.thread.is_alive())
        self.assertEqual(seen, [])
        worker.drain()
        self.assertEqual([row[0] for row in seen], ["progress", "result"])
        for _, callback_thread, job_thread in seen:
            self.assertEqual(callback_thread, main_thread)
            self.assertNotEqual(job_thread, main_thread)

    def test_persistent_loop_and_error_delivery(self):
        worker = BackgroundWorker()
        results, errors = [], []
        async def operation(report):
            return asyncio.get_running_loop()
        worker.submit(operation, results.append, errors.append)
        worker.submit(lambda report: 1 / 0, results.append, errors.append)
        worker.submit(operation, results.append, errors.append)
        worker.close()
        worker.thread.join(3)
        self.assertFalse(worker.thread.is_alive())
        worker.drain()
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assertIsInstance(errors[0], ZeroDivisionError)
        with self.assertRaises(RuntimeError):
            worker.submit(operation, results.append, errors.append)


class CompletionTests(unittest.TestCase):
    def test_login_queues_authentication_and_prevents_duplicate_clicks(self):
        button = Mock()
        button.instate.return_value = False
        page = SimpleNamespace(controller=SimpleNamespace(closing=False, worker=Mock()),
                               login_button=button, status=Mock(),
                               _logged_in=Mock(), _login_failed=Mock())
        with patch("app.pages.login_page.authenticate") as authenticate:
            LoginPage.login(page)
            authenticate.assert_not_called()
            job = page.controller.worker.submit.call_args.args[0]
            job(Mock())
            authenticate.assert_called_once()
            button.instate.return_value = True
            LoginPage.login(page)
            page.controller.worker.submit.assert_called_once()

    def test_completion_preserves_settings_edited_during_run(self):
        page = SimpleNamespace(_set_busy=Mock(), status=Mock(), progress=Mock(), _refresh_sift_options=Mock())
        options = {"rules": ["newly edited rule"], "dark_mode": True}
        result = SiftResult(2, 1, 1, {"last_sift_at": "2026-01-01T00:00:00Z"})
        with patch("app.pages.main_page.loadUserOptions", return_value=options), \
             patch("app.pages.main_page.saveUserOptions") as save:
            MainPage._sift_finished(page, result)
        self.assertEqual(save.call_args.args[0]["rules"], ["newly edited rule"])
        self.assertTrue(save.call_args.args[0]["dark_mode"])

    def test_success_fills_progress_even_for_empty_inbox(self):
        for examined in (0, 1, 100):
            with self.subTest(examined=examined):
                state = {"mode": "indeterminate", "maximum": 100, "value": 7}
                page = SimpleNamespace(
                    _set_busy=Mock(), status=Mock(), _refresh_sift_options=Mock(),
                    progress=SimpleNamespace(config=lambda **kwargs: state.update(kwargs)),
                )
                with patch("app.pages.main_page.loadUserOptions", return_value={}), \
                     patch("app.pages.main_page.saveUserOptions"):
                    MainPage._sift_finished(page, SiftResult(examined, 0, 0, {}))
                self.assertEqual(state["mode"], "determinate")
                self.assertEqual(state["value"], state["maximum"])

    def test_failure_and_cancel_do_not_save_checkpoint(self):
        page = SimpleNamespace(_set_busy=Mock(), status=Mock())
        with patch("app.pages.main_page.saveUserOptions") as save:
            for error in (SiftCancelled(), RuntimeError("network failure")):
                MainPage._sift_failed(page, error)
            save.assert_not_called()
