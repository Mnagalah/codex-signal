import argparse,copy,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import test_project_controls as fixtures
from test_state import snapshot
from main import Plugin
from control import enqueue

class GlobalControlTests(unittest.TestCase):
    plugin=fixtures.ProjectControlTests.plugin
    def phases(self,p):return [c['status'] for g in p.last_status['projects'] for c in g['threads']]

    def test_master_resume_covers_connection_and_fresh_snapshot_without_false_unknown(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved())
                p.consume_ui({'event':'disable'});self.assertFalse(p.enabled);self.assertFalse(self.phases(p))
                p.consume_ui({'event':'enable'})
                self.assertFalse(p.connected);self.assertTrue(p.resume_connecting);self.assertFalse(self.phases(p))
                self.assertEqual(p.registry.saved(),before)
                self.assertTrue(all(x['syncing'] for x in p.last_status['projectControls']))
                self.assertEqual([c['status'] for g in p.last_status['projectControls'] for c in g['threads']],['syncing','syncing'])
                p.connected=True;p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertFalse(p.resume_connecting);self.assertEqual(self.phases(p),['approval'])
                p.states['remote::b'].consume(snapshot(),'owner');p.publish()
                self.assertEqual(self.phases(p),['approval','running']);self.assertFalse(p.resume_snapshots)
                self.assertEqual(p.notice_emitted,0)
            finally:p.lock.close()

    def test_master_timeout_and_real_connection_failure_show_unknown_not_loading(self):
        for failure in ('timeout','connection'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
                p=self.plugin()
                try:
                    p.control('disable')
                    with patch('main.time.monotonic',return_value=100):p.control('enable')
                    if failure=='timeout':
                        with patch('main.time.monotonic',return_value=105.1):p.publish()
                    else:
                        with patch('main.DesktopIPC') as cls:
                            cls.return_value.connect.side_effect=PermissionError(1,'denied')
                            p.connect();p.publish()
                    self.assertFalse(p.resume_snapshots);self.assertFalse(p.resume_connecting)
                    self.assertEqual(self.phases(p),['unknown','unknown'])
                finally:p.lock.close()

    def test_master_keeps_paused_project_choice_and_quick_off_cancels_pending(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_project_updates('remote::p',False);p.control('disable');p.control('enable')
                self.assertEqual(set(p.resume_snapshots),{'a'})
                p.control('disable');self.assertFalse(p.resume_snapshots)
                p.states['a'].consume(snapshot(),'owner');p.publish();self.assertFalse(self.phases(p))
                p.control('enable');self.assertIn('remote::p',p.paused_projects)
                self.assertEqual(set(p.resume_snapshots),{'a'})
                p.connected=True;p.states['a'].consume(snapshot(),'owner');p.publish()
                self.assertEqual(self.phases(p),['running'])
            finally:p.lock.close()

    def test_enabled_payload_startup_holds_retained_ids_before_states_are_loaded(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin();saved=copy.deepcopy(p.registry.saved());p.lock.close()
            q=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                q.elect();q.publish()
                self.assertEqual(set(q.resume_snapshots),set(saved['entries']))
                self.assertEqual(q.last_status['projects'],[]);self.assertEqual(q.registry.saved(),saved)
                self.assertTrue(all(c['status']=='syncing' for g in q.last_status['projectControls'] for c in g['threads']))
            finally:q.lock.close()

    def test_actual_compact_commands_change_only_presentation_and_preserve_snapshot_handoff(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved());calls=list(p.ipc.calls)
                for action,want in [('compact-on',True),('compact-off',False)]:
                    enqueue(Path(tmp),action);p.consume_commands()
                    self.assertEqual(p.compact_menu_bar,want);self.assertEqual(p.registry.saved(),before)
                    self.assertEqual(p.ipc.calls,calls);self.assertEqual(self.phases(p),['running','running'])
                p.control('disable');p.control('enable');pending=dict(p.resume_snapshots)
                enqueue(Path(tmp),'compact-on');p.consume_commands()
                self.assertEqual(p.resume_snapshots,pending);self.assertTrue(p.resume_connecting)
            finally:p.lock.close()
