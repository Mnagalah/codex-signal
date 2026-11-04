import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import test_project_controls as fixtures
from test_state import snapshot
from control import enqueue,pending

class ResumeProbeTests(unittest.TestCase):
    plugin=fixtures.ProjectControlTests.plugin

    def test_project_target_required_only_for_explicit_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for value in (None,'','bad\nvalue','x'*257):
                with self.assertRaises(ValueError):enqueue(root,'exercise-project',project_id=value)
            with self.assertRaises(ValueError):enqueue(root,'reload',project_id='p')
            enqueue(root,'exercise-project',project_id='remote::p')
            enqueue(root,'reload')
            values=list(pending(root))
            self.assertEqual(values[0]['projectId'],'remote::p')
            self.assertNotIn('projectId',values[1])

    def test_probe_is_explicit_and_rejects_unready_paused_and_unknown_targets(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.ui_ready=True
                with patch.dict(os.environ,{'CODEX_MENU_STATUS_CAPTURE':'0'}):self.assertFalse(p.start_resume_probe('ticket','p'))
                with patch.dict(os.environ,{'CODEX_MENU_STATUS_CAPTURE':'1'}):
                    self.assertFalse(p.start_resume_probe('ticket','missing'))
                    p.set_project_updates('p',False);self.assertFalse(p.start_resume_probe('ticket','p'))
                    p.set_project_updates('p',True);p.resume_snapshots.clear();p.publish()
                    self.assertFalse(p.start_resume_probe('ticket','p'))
                    p.states['a'].consume(snapshot(),'owner');p.publish()
                    self.assertTrue(p.start_resume_probe('ticket','p'))
                    p.finish_resume_probe(False,'test-cleanup')
            finally:p.lock.close()

    def test_bounded_real_switch_path_restores_selected_project_without_chat_actions(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            p=self.plugin()
            try:
                p.ui_ready=True;before=copy.deepcopy(p.registry.saved())
                self.assertTrue(p.start_resume_probe('ticket','p'));clock=p.resume_probe.started
                for offset in (0,0.31,0.32,0.58,0.65,0.66,0.92):
                    if offset in (0.32,0.66):p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                    p.tick_resume_probe(clock+offset)
                self.assertIsNone(p.resume_probe)
                report=json.loads((Path(tmp)/'render-check/project-resume-ticket.json').read_text())
                self.assertTrue(report['completed']);self.assertTrue(report['restoredProjectEnabled'])
                self.assertEqual(p.ipc.calls,[('local','a',False),('local','a',True)]*2)
                self.assertTrue(any(s['syncing'] and not s['menu'] for s in report['samples']))
                self.assertTrue(all(c['status']!='unknown' for s in report['samples'] for c in s['menu']))
                self.assertEqual(p.registry.next_number,before['nextNumber'])
                self.assertEqual(p.registry.entries['a']['index'],before['entries']['a']['index'])
                self.assertEqual(p.notice_emitted,0)
            finally:p.lock.close()

    def test_user_preference_change_cancels_probe_then_applies_users_latest_intent(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            p=self.plugin()
            try:
                p.ui_ready=True;p.start_resume_probe('ticket','p');p.tick_resume_probe(time.monotonic())
                self.assertIn('p',p.paused_projects)
                p.consume_ui({'event':'project_disable','projectId':'p'})
                self.assertIsNone(p.resume_probe);self.assertIn('p',p.paused_projects)
                report=json.loads((Path(tmp)/'render-check/project-resume-ticket.json').read_text())
                self.assertFalse(report['completed']);self.assertEqual(report['reason'],'user-interaction')
                self.assertEqual(p.ipc.calls,[('local','a',False),('local','a',True),('local','a',False)])
            finally:p.lock.close()

    def test_timeout_or_global_control_restores_probe_owned_preference(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            p=self.plugin()
            try:
                p.ui_ready=True;p.start_resume_probe('timeout','p');started=p.resume_probe.started
                p.tick_resume_probe(started);p.tick_resume_probe(started+14)
                self.assertNotIn('p',p.paused_projects);self.assertIsNone(p.resume_probe)
                p.states['a'].consume(snapshot(),'owner');p.publish()
                p.start_resume_probe('control','p');p.tick_resume_probe(time.monotonic());p.control('disable')
                self.assertNotIn('p',p.paused_projects);self.assertFalse(p.enabled);self.assertIsNone(p.resume_probe)
            finally:p.lock.close()
