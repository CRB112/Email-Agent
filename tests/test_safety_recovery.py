import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.agents.microsoft import MicrosoftGraphAgent
from app.parser.MatchCommands import COMMAND_CLASSES
from app.rules.validation import validate_options, validate_rule
from app.services.execution import ProcessingFailure
from app.services.journal import RunJournal
from app.services.sifting import sift
from appROOT import MainWindow
from tests.fakes import FakeGraph, make_email, make_rule


class ValidationTests(unittest.TestCase):
    def test_empty_and_blank_keywords_cannot_match_everything(self):
        for words in ([], [''], ['  '], 'invoice', [None]):
            for mode in ('Any', 'All'):
                with self.subTest(words=words, mode=mode), self.assertRaises(ValueError):
                    validate_rule(make_rule(settings={'Words': words, 'Type': mode}))
                with self.subTest(words=words, mode=mode), self.assertRaises(ValueError):
                    COMMAND_CLASSES['match_subject_contains']({'Words': words, 'Type': mode})

    def test_bad_destinations_mark_values_and_unknown_commands(self):
        invalid = [make_rule(actions={'Move': {'Folder': ''}}),
                   make_rule(actions={'Mark': {'Mark_type': 'Read', 'Mark_op': 'High'}}),
                   make_rule(actions={'Unknown': {}}), make_rule(actions={}),
                   make_rule(match_type='unknown')]
        for rule in invalid:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                validate_rule(rule)

    def test_invalid_settings_shapes_and_limits(self):
        for options in ([], {'rules': {}}, {'rules': [None]}, {'max_emails': True},
                        {'max_emails': 0}, {'max_emails': 10001}, {'schema_version': 2},
                        {'last_sift_at': '2026-01-01'}, {'last_sift_ids': 'id'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                validate_options(options)

    def test_exact_matchers_tolerate_missing_sender_parts(self):
        for sender in (None, SimpleNamespace(email_address=None), SimpleNamespace(email_address=SimpleNamespace(address=None))):
            email = make_email()
            email.from_ = sender
            for kind, settings in (('match_sender', {'Sender': 'a@b.com'}), ('match_domain', {'Domain': 'b.com'})):
                self.assertFalse(COMMAND_CLASSES[kind](settings).testMatch(email))

    def test_bundled_defaults_have_no_active_actions(self):
        defaults = json.loads((Path(__file__).resolve().parents[1] / 'app/user/useroptions.json').read_text())
        validate_options(defaults)
        self.assertEqual(defaults['rules'], [])


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.graph = FakeGraph()
        self.agent = MicrosoftGraphAgent(self.graph)
        self.agent.mailbox_key = 'microsoft:test-account'
        self.journal = RunJournal(self.agent.mailbox_key, directory.name)
        self.agent.get_emails = AsyncMock(return_value=[make_email(subject='Invoice')])
        self.options = {'rules': [make_rule(actions={'Mark': {'Mark_type': 'Read'}, 'Move': {'Folder': 'archive'}, 'Delete': {}})]}

    async def run_sift(self, **kwargs):
        return await sift(self.agent, self.options, 'since_last', Event(), Mock(), journal=self.journal, **kwargs)

    async def test_preview_is_read_only_and_apply_uses_frozen_actions(self):
        preview = await self.run_sift(preview=True)
        self.assertEqual(self.graph.actions, [])
        self.assertIsNone(self.journal.load())
        self.options['rules'] = [make_rule(actions={'Delete': {}})]
        result = await self.run_sift(prepared=preview.batch)
        self.assertEqual([action['action'] for action in self.graph.actions], ['Mark', 'Move', 'Delete'])
        self.assertEqual(result.modifications, 3)
        self.agent.get_emails.assert_awaited_once()

    async def test_failure_keeps_successes_and_resumes_after_move(self):
        self.graph.fail_on = 'Delete'
        with self.assertRaises(ProcessingFailure):
            await self.run_sift()
        batch = self.journal.load()
        self.assertEqual([step['status'] for step in batch['records'][0]['actions']], ['done', 'done', 'uncertain'])
        self.assertEqual(batch['records'][0]['current_id'], 'moved-email-1')
        self.graph.fail_on = None
        with self.assertRaisesRegex(ProcessingFailure, 'Review uncertain'):
            await self.run_sift()
        self.journal.resolve('email-1', 2, completed=False)
        self.agent.get_emails.return_value = []  # Message has already left Inbox.
        result = await self.run_sift()
        self.assertEqual([action['action'] for action in self.graph.actions], ['Mark', 'Move', 'Delete'])
        self.assertEqual(self.graph.actions[-1]['email_id'], 'moved-email-1')
        self.assertEqual(result.modified, 1)

    async def test_uncertain_success_can_be_marked_completed_without_replay(self):
        self.graph.fail_on = 'Delete'
        with self.assertRaises(ProcessingFailure):
            await self.run_sift()
        self.journal.resolve('email-1', 2, completed=True)
        await self.run_sift()
        self.assertEqual(len(self.graph.actions), 2)

    async def test_completion_is_retained_until_checkpoint_commit(self):
        result = await self.run_sift()
        await self.run_sift()
        self.assertEqual(len(self.graph.actions), 3)
        self.assertIsNotNone(self.journal.load())
        self.journal.acknowledge(result.batch['batch_id'])
        self.assertIsNone(self.journal.load())
        self.assertEqual(self.journal.last_completed_id(), result.batch['batch_id'])

    async def test_already_applied_preview_cannot_be_replayed(self):
        preview = await self.run_sift(preview=True)
        result = await self.run_sift(prepared=preview.batch)
        self.journal.acknowledge(result.batch['batch_id'])
        with self.assertRaisesRegex(ValueError, 'stale or already applied'):
            await self.run_sift(prepared=preview.batch)
        self.assertEqual(len(self.graph.actions), 3)

    async def test_uncertain_is_written_before_request_and_survives_interruption(self):
        original = self.graph.record
        def record(*args, **kwargs):
            batch = self.journal.load()
            self.assertIn('uncertain', [step['status'] for step in batch['records'][0]['actions']])
            original(*args, **kwargs)
        self.graph.record = record
        await self.run_sift()
        self.assertEqual(self.journal.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('body', self.journal.path.read_text())

    async def test_preflight_rejects_destinations_before_marking(self):
        self.options['rules'][0]['modify']['Move']['Folder'] = 'does-not-exist'
        self.agent.list_destinations = AsyncMock(return_value={'Archive': 'archive'})
        with self.assertRaisesRegex(ProcessingFailure, 'Unknown destination'):
            await self.run_sift()
        self.assertEqual(self.graph.actions, [])
        self.assertIsNone(self.journal.load())

    async def test_disk_failure_before_request_cannot_modify_mail(self):
        with patch.object(self.journal, 'save', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                await self.run_sift()
        self.assertEqual(self.graph.actions, [])

    async def test_wrong_mailbox_preview_is_rejected(self):
        preview = await self.run_sift(preview=True)
        preview.batch['mailbox_key'] = 'gmail:someone-else'
        with self.assertRaisesRegex(ValueError, 'different mailbox'):
            await self.run_sift(prepared=preview.batch)

    async def test_simultaneous_runs_are_rejected(self):
        with self.journal.lock():
            with self.assertRaisesRegex(RuntimeError, 'Another window'):
                await self.run_sift()

    async def test_commit_preserves_edits_and_recovers_from_settings_failure(self):
        from app.parser import parser
        result = await self.run_sift()
        directory = self.journal.path.parent
        with patch.object(parser, 'USER_OPTIONS_DIR', directory), \
             patch.object(parser, 'OPTIONS_FILE', directory / 'settings.json'):
            parser.saveUserOptions({'rules': [], 'dark_mode': True, 'mailbox_key': self.agent.mailbox_key})
            with patch.object(parser, 'saveUserOptions', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    self.journal.commit(result.batch['batch_id'])
            self.assertIsNotNone(self.journal.load())
            self.journal.commit(result.batch['batch_id'])
            saved = parser.loadUserOptions()
            self.assertEqual(saved['rules'], [])
            self.assertTrue(saved['dark_mode'])
            self.assertEqual(saved['last_sift_at'], result.settings_update['last_sift_at'])
            self.assertIsNone(self.journal.load())
            self.journal.commit(result.batch['batch_id'])  # Duplicate UI callback is harmless.
            self.assertEqual(len(self.graph.actions), 3)

    async def test_cancellation_resumes_pending_messages_without_replay(self):
        from app.services.control import SiftCancelled
        self.agent.get_emails.return_value = [make_email(id='first', subject='Invoice'), make_email(id='second', subject='Invoice')]
        self.options = {'rules': [make_rule()]}
        cancel = Event()
        def report(_text, done, total):
            if done == 1 and total == 2:
                cancel.set()
        with self.assertRaises(SiftCancelled):
            await sift(self.agent, self.options, 'since_last', cancel, report, journal=self.journal)
        self.assertEqual(len(self.graph.actions), 1)
        await self.run_sift()
        self.assertEqual([action['email_id'] for action in self.graph.actions], ['first', 'second'])

    async def test_preview_exposes_invalid_destinations_without_mutating(self):
        self.options['rules'][0]['modify']['Move']['Folder'] = 'missing'
        self.agent.list_destinations = AsyncMock(return_value={'Archive': 'archive'})
        result = await self.run_sift(preview=True)
        self.assertIn('Unknown destination', result.warnings[0])
        self.assertEqual(len(result.records), 1)
        self.assertEqual(self.graph.actions, [])

    async def test_resolution_from_stale_preview_cannot_edit_another_batch(self):
        self.graph.fail_on = 'Delete'
        with self.assertRaises(ProcessingFailure):
            await self.run_sift()
        with self.assertRaisesRegex(ValueError, 'Recovery changed'):
            self.journal.resolve('email-1', 2, True, batch_id='stale')
        self.assertEqual(self.journal.load()['records'][0]['actions'][2]['status'], 'uncertain')

    async def test_corrupt_recovery_is_rejected_before_modifying_mail(self):
        preview = await self.run_sift(preview=True)
        batch = preview.batch
        batch['records'][0]['actions'][-1]['action'] = 'Unknown'
        self.journal.save(batch)
        with self.assertRaisesRegex(ValueError, 'Recovery record is invalid'):
            await self.run_sift()
        self.assertEqual(self.graph.actions, [])

    async def test_unavailable_well_known_folder_fails_before_marking(self):
        self.graph.by_mail_folder_id = Mock(return_value=SimpleNamespace(get=AsyncMock(return_value=None)))
        with self.assertRaisesRegex(ProcessingFailure, 'folder is unavailable'):
            await self.run_sift()
        self.assertEqual(self.graph.actions, [])


class ShutdownTests(unittest.TestCase):
    def test_closing_drains_completion_before_destroying(self):
        calls = []
        window = SimpleNamespace(closing=True, worker=SimpleNamespace(
            drain=lambda: calls.append('completion'), thread=SimpleNamespace(is_alive=lambda: False)),
            destroy=lambda: calls.append('destroy'), after=Mock())
        MainWindow._poll_worker(window)
        self.assertEqual(calls[-1], 'destroy')
        self.assertIn('completion', calls[:-1])

    def test_closing_keeps_processing_completions_while_worker_is_alive(self):
        window = SimpleNamespace(closing=True, worker=SimpleNamespace(
            drain=Mock(), thread=SimpleNamespace(is_alive=lambda: True)), destroy=Mock(), after=Mock(), _poll_worker=Mock())
        MainWindow._poll_worker(window)
        window.worker.drain.assert_called_once()
        window.destroy.assert_not_called()
        window.after.assert_called_once()
