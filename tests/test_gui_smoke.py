"""Real Tk widgets and worker flow; run under xvfb-run in CI."""
import gc
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import AsyncMock, patch

from app.agents.microsoft import MicrosoftGraphAgent
from app.parser import parser
from appROOT import MainWindow
from tests.fakes import FakeGraph, make_email, make_rule
from app.widgets.rule_editor import RuleEditor
from app.widgets.rule_card import RuleCard


@unittest.skipUnless(os.environ.get('EMAIL_AGENT_GUI_TESTS') == '1', 'Run with EMAIL_AGENT_GUI_TESTS=1 under a display or Xvfb')
class GuiSmokeTests(unittest.TestCase):
    def test_preview_apply_persist_and_logout_with_real_widgets(self):
        with TemporaryDirectory() as directory:
            with patch.object(parser, 'USER_OPTIONS_DIR', Path(directory)), \
                 patch.object(parser, 'OPTIONS_FILE', Path(directory) / 'useroptions.json'):
                parser.saveUserOptions({'rules': [make_rule()], 'max_emails': 10})
                app = MainWindow()
                app.withdraw()
                try:
                    graph = FakeGraph()
                    agent = MicrosoftGraphAgent(graph)
                    agent.mailbox_key = 'microsoft:gui-test'
                    agent.get_emails = AsyncMock(return_value=[make_email(subject='Invoice')])
                    agent.list_destinations = AsyncMock(return_value={'Archive': 'archive'})
                    app.email_agent = agent
                    app.worker.register_resource(agent)
                    app.show_page('Main')
                    main = app.pages['Main']

                    def wait_for(predicate):
                        deadline = time.monotonic() + 5
                        while not predicate():
                            if time.monotonic() >= deadline:
                                self.fail('GUI operation timed out')
                            app.update()
                            time.sleep(0.01)

                    wait_for(lambda: not main.loading_destinations)
                    self.assertEqual(main.destinations, {'Archive': 'archive'})
                    app.geometry('760x520')
                    main.notebook.select(main.rules_tab)
                    app.deiconify()
                    app.update()
                    main.show_new_rule_editor()
                    box = main.rules_list.content.winfo_children()[0]
                    editor = next(child for child in box.winfo_children() if isinstance(child, RuleEditor))
                    self.assertEqual(editor.action_editor.values(), {})
                    editor.action_editor.add_buttons['Mark'].invoke()
                    editor.save()
                    self.assertIn('at least one keyword', editor.error.cget('text'))
                    editor.action_editor.add_buttons['Move'].invoke()
                    folder = editor.action_editor._editors['Move']._fields['Folder']
                    self.assertEqual(str(folder['widget'].cget('state')), 'readonly')
                    folder['variable'].set('Archive')
                    self.assertEqual(editor.action_editor.values()['Move']['Folder'], 'archive')

                    # Controls stay within the scrollable area at the minimum window width.
                    app.update()
                    canvas = main.rules_list.canvas
                    for button in editor.action_editor.add_buttons.values():
                        self.assertTrue(button.winfo_ismapped())
                        self.assertGreaterEqual(button.winfo_rootx(), canvas.winfo_rootx())
                        self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                             canvas.winfo_rootx() + canvas.winfo_width())

                    # An added Delete action can be removed and added again.
                    editor.action_editor.add_buttons['Delete'].invoke()
                    self.assertIn('Delete', editor.action_editor.values())
                    editor.action_editor.remove_buttons['Delete'].invoke()
                    self.assertNotIn('Delete', editor.action_editor.values())
                    self.assertFalse(editor.action_editor.add_buttons['Delete'].instate(['disabled']))

                    # Adding/removing another action preserves the Mark selections.
                    mark = editor.action_editor._editors['Mark']
                    mark.mark_type_display.set('Importance')
                    mark.type_editor.event_generate('<<ComboboxSelected>>')
                    self.assertEqual(tuple(mark.op_editor['values']), ('Low', 'Normal', 'High'))
                    self.assertEqual(mark.mark_op.get(), 'Normal')
                    mark.mark_op.set('High')
                    mark.op_editor.event_generate('<<ComboboxSelected>>')
                    self.assertIn('High sets Important', mark.help_label.cget('text'))
                    editor.action_editor.remove_buttons['Move'].invoke()
                    self.assertEqual(editor.action_editor.values(), {
                        'Mark': {'Mark_type': 'Importance', 'Mark_op': 'High'},
                    })
                    mark = editor.action_editor._editors['Mark']
                    mark.mark_type_display.set('Read status')
                    mark.type_editor.event_generate('<<ComboboxSelected>>')
                    self.assertEqual(tuple(mark.op_editor['values']), ('Read', 'Unread'))
                    mark.mark_op.set('Unread')
                    mark.op_editor.event_generate('<<ComboboxSelected>>')
                    self.assertIn('marked as unread', mark.help_label.cget('text'))
                    editor.condition_editor._fields['Words']['variable'].set('receipt')
                    editor.save()
                    saved_rule = parser.loadUserOptions()['rules'][-1]
                    self.assertEqual(saved_rule['modify'], {'Mark': {'Mark_type': 'Read', 'Mark_op': 'Unread'}})

                    # An existing rule with only Delete exposes the same editing controls.
                    parser.saveUserOptions({'rules': [make_rule(actions={'Delete': {}})], 'max_emails': 10})
                    main.refresh_rules()
                    card = next(child for child in main.rules_list.content.winfo_children() if isinstance(child, RuleCard))
                    card.show_editor()
                    actions = card.editor.action_editor
                    actions.remove_buttons['Delete'].invoke()
                    self.assertEqual(actions.values(), {})
                    actions.add_buttons['Mark'].invoke()
                    card.editor.save()
                    self.assertEqual(parser.loadUserOptions()['rules'][0]['modify'], {
                        'Mark': {'Mark_type': 'Read', 'Mark_op': 'Read'},
                    })

                    # Restore the single-rule fixture for the preview/apply checks.
                    parser.saveUserOptions({'rules': [make_rule()], 'max_emails': 10})
                    main.refresh_rules()
                    main.dark_mode.set(True)
                    main.toggle_dark_mode()
                    # Finalize destroyed editor variables on Tk's owning thread.
                    gc.collect()
                    main.attempt_go()
                    wait_for(lambda: not main.sifting)
                    self.assertIsNotNone(main.preview_result)
                    self.assertEqual(graph.actions, [])
                    self.assertEqual(len(main.results.get_children()), 1)
                    main.apply_preview()
                    wait_for(lambda: not main.sifting)
                    self.assertEqual(len(graph.actions), 1)
                    self.assertIn('last_sift_at', parser.loadUserOptions())
                    self.assertTrue(parser.loadUserOptions()['dark_mode'])
                    self.assertIsNone(main.preview_result)
                    main.logout()
                    wait_for(lambda: not main.sifting)
                    self.assertIsNone(app.email_agent)
                finally:
                    app.close()
                    app.worker.thread.join(5)
                    if app.winfo_exists():
                        app._poll_worker()
