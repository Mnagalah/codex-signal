import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from main import Plugin
from state import ThreadState,WatchRegistry
from test_state import snapshot

class Followers:
    def __init__(self):self.following={('local','a'),('remote','b')};self.calls=[]
    def follow(self,tid,enabled=True,*,host_id='local'):
        self.calls.append((host_id,tid,enabled))
        if enabled:self.following.add((host_id,tid))
        else:self.following.discard((host_id,tid))
    def close(self):self.following.clear()

class ProjectControlTests(unittest.TestCase):
    def plugin(self):
        p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
        a=ThreadState('a');a.consume(snapshot(),'owner')
        b=ThreadState('b',host_id='remote');b.consume(snapshot(),'owner')
        p.states={'a':a,'remote::b':b}
        identities={'a':{'id':'p','name':'原始项目','markerType':'icon','marker':'folder'},
                    'remote::b':{'id':'remote::p','name':'原始项目','markerType':'icon','marker':'folder','hostId':'remote'}}
        p.metadata=types.SimpleNamespace(identities=lambda _:identities)
        p.connected=True;p.ipc=Followers();p.publish()
        return p

    def test_project_pause_releases_only_its_follower_and_retains_records(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved());p.registry.acknowledged['old']='turn'
                p.consume_ui({'event':'project_disable','projectId':'p'})
                self.assertTrue(p.enabled);self.assertTrue(p.connected)
                self.assertEqual([g['id'] for g in p.last_status['projects']],['remote::p'])
                self.assertEqual(p.ipc.calls,[('local','a',False)])
                self.assertEqual(p.registry.entries['a'],before['entries']['a'])
                self.assertEqual(p.registry.next_number,before['nextNumber'])
                self.assertEqual(p.registry.acknowledged,{'old':'turn'})
                self.assertEqual(len(p.last_status['projectControls']),2)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(p.notice_emitted,0)
                self.assertEqual(p.registry.entries['a']['phase'],'running')
            finally:p.lock.close()

    def test_project_resume_rebaselines_without_replaying_paused_changes(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                index=p.registry.entries['a']['index']
                p.set_project_updates('p',False)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner')
                p.set_project_updates('p',True)
                self.assertFalse(p.states['a'].valid);self.assertIn(('local','a',True),p.ipc.calls)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(p.notice_emitted,0)
                p.states['a'].consume(snapshot(flags=['waitingOnUserInput']),'owner');p.publish()
                self.assertEqual(p.notice_emitted,1)
                self.assertEqual(p.registry.entries['a']['index'],index)
            finally:p.lock.close()

    def test_master_toggle_preserves_project_choices_and_unknown_preferences(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            path=Path(tmp)/'settings.json';path.write_text(json.dumps({'enabled':True,'futurePreference':'retained'}))
            p=self.plugin()
            try:
                p.set_project_updates('p',False);p.control('disable')
                self.assertFalse(p.enabled);self.assertEqual(p.last_status['projects'],[])
                self.assertEqual(len(p.last_status['projectControls']),2)
                p.control('enable')
                saved=json.loads(path.read_text())
                self.assertTrue(saved['enabled']);self.assertIn('p',saved['pausedProjects'])
                self.assertEqual(saved['futurePreference'],'retained')
                self.assertFalse(next(x for x in p.last_status['projectControls'] if x['id']=='p')['updatesEnabled'])
            finally:p.lock.close()

    def test_reloaded_preferences_keep_paused_projects_and_host_identity(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin();p.set_project_updates('remote::p',False)
            saved=copy.deepcopy(p.registry.saved());p.lock.close()
            q=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                q.elect();self.assertIn('remote::p',q.paused_projects)
                self.assertEqual(q.registry.saved(),saved)
                self.assertTrue(q.project_paused('remote::b'));self.assertFalse(q.project_paused('a'))
                q.publish()
                self.assertEqual({x['id'] for x in q.last_status['projectControls']},{'p','remote::p'})
            finally:q.lock.close()

    def test_unrecognized_project_cannot_change_preferences_or_other_notice(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.notice_target=('notice','remote::b')
                p.pending_notice={'id':'n','project':{'id':'remote::p'},'chat':{'id':'remote::b','status':'input'}}
                p.consume_ui({'event':'project_disable','projectId':'not-a-project'})
                self.assertFalse(p.paused_projects);self.assertFalse((Path(tmp)/'settings.json').exists())
                p.set_project_updates('p',False)
                self.assertEqual(p.notice_target,('notice','remote::b'))
                self.assertEqual(p.pending_notice['id'],'n')
                p.set_project_updates('remote::p',False)
                self.assertIsNone(p.notice_target);self.assertIsNone(p.pending_notice)
            finally:p.lock.close()

    def test_notification_choices_filter_edges_without_replaying_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_notification_state('approval',False)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(p.notice_emitted,0)
                p.set_notification_state('approval',True);self.assertEqual(p.notice_emitted,0)
                p.states['a'].consume(snapshot(flags=['waitingOnUserInput']),'owner');p.publish()
                self.assertEqual(p.notice_emitted,1)
                for phase in list(p.notification_states):p.set_notification_state(phase,False)
                self.assertFalse(p.last_status['notifications']['enabled'])
                self.assertEqual(len(p.last_status['projects']),2)
                p.states['a'].consume(snapshot(),'owner');p.publish()
                self.assertEqual(p.notice_emitted,1)
            finally:p.lock.close()

    def test_compact_presentation_keeps_transport_chat_states_and_local_records(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved());calls=list(p.ipc.calls)
                p.consume_ui({'event':'compact_enable'})
                self.assertTrue(p.last_status['compactMenuBar'])
                self.assertEqual(p.registry.saved(),before);self.assertEqual(p.ipc.calls,calls)
                self.assertEqual(len(p.last_status['projects']),2)
                self.assertEqual(p.last_status['projectControls'][0]['threads'][0]['id'],'a')
                p.set_notification_state('running',False);p.set_project_updates('p',False)
                saved=json.loads((Path(tmp)/'settings.json').read_text())
                self.assertTrue(saved['compactMenuBar']);self.assertNotIn('running',saved['notificationStates'])
                self.assertIn('p',saved['pausedProjects'])
                p.consume_ui({'event':'compact_disable'})
                self.assertFalse(p.compact_menu_bar);self.assertNotIn('running',p.notification_states)
            finally:p.lock.close()

    def test_disabling_one_notice_type_clears_only_its_own_pending_click(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.notice_target=('n','a');p.notice_phase='approval'
                p.pending_notice={'id':'other','project':{'id':'p'},'chat':{'id':'a','status':'input'}}
                p.set_notification_state('approval',False)
                self.assertIsNone(p.notice_target);self.assertIsNotNone(p.pending_notice)
                p.set_notification_state('input',False);self.assertIsNone(p.pending_notice)
                self.assertTrue(p.enabled)
            finally:p.lock.close()

    def test_empty_alert_selection_and_compact_mode_survive_a_reload(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            for phase in list(p.notification_states):p.set_notification_state(phase,False)
            p.consume_ui({'event':'compact_enable'});p.lock.close()
            q=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                q.elect();q.publish()
                self.assertEqual(q.notification_states,set());self.assertTrue(q.compact_menu_bar)
                self.assertFalse(q.last_status['notifications']['enabled'])
                self.assertEqual(len(q.last_status['projectControls']),2)
            finally:q.lock.close()

    def test_custom_status_emoji_persists_without_changing_project_icons_or_task_records(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved())
                self.assertEqual(p.status_emoji,'🔦')
                p.consume_ui({'event':'set_status_emoji','emoji':'👩🏽‍💻'})
                self.assertEqual(p.last_status['statusEmoji'],'👩🏽‍💻')
                self.assertEqual(p.registry.saved(),before)
                p.consume_ui({'event':'set_status_emoji','emoji':'bad\nvalue'})
                self.assertEqual(p.status_emoji,'👩🏽‍💻')
                self.assertEqual(json.loads((Path(tmp)/'settings.json').read_text())['statusEmoji'],'👩🏽‍💻')
            finally:p.lock.close()

class ResumeColorTests(unittest.TestCase):
    plugin = ProjectControlTests.plugin
    def menu_phases(self,p,pid='p'):
        return [c['status'] for group in p.last_status['projects'] if group['id']==pid for c in group['threads']]
    def control(self,p,pid='p'):
        return next(x for x in p.last_status['projectControls'] if x['id']==pid)

    def test_resume_waits_for_a_usable_snapshot_without_persisting_false_unknown(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                before=copy.deepcopy(p.registry.saved());since=before['entries']['a']['since']
                p.set_project_updates('p',False);p.set_project_updates('p',True)
                for _ in range(3):
                    p.publish();self.assertEqual(self.menu_phases(p),[])
                    self.assertTrue(self.control(p)['syncing'])
                    self.assertEqual(self.control(p)['threads'][0]['status'],'syncing')
                    self.assertFalse(self.control(p)['threads'][0]['canMarkSeen'])
                    self.assertEqual(p.registry.saved(),before)
                self.assertTrue(p.refresh_pending)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),['approval']);self.assertFalse(self.control(p)['syncing'])
                self.assertEqual(p.registry.entries['a']['index'],before['entries']['a']['index'])
                self.assertEqual(p.registry.entries['a']['firstSeen'],before['entries']['a']['firstSeen'])
                self.assertEqual(p.notice_emitted,0)
                self.assertNotIn('resume_snapshots',json.loads((Path(tmp)/'settings.json').read_text()))
            finally:p.lock.close()

    def test_not_loaded_snapshot_stays_syncing_then_timeout_exposes_honest_unknown(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_project_updates('p',False)
                with patch('main.time.monotonic',return_value=100):p.set_project_updates('p',True)
                p.states['a'].consume(snapshot(kind='notLoaded'),'owner')
                with patch('main.time.monotonic',return_value=104.9):p.publish()
                self.assertEqual(self.menu_phases(p),[]);self.assertTrue(self.control(p)['syncing'])
                with patch('main.time.monotonic',return_value=105.1):p.publish()
                self.assertEqual(self.menu_phases(p),['unknown']);self.assertFalse(self.control(p)['syncing'])
                p.states['a'].consume(snapshot(flags=['waitingOnUserInput']),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),['input']);self.assertEqual(p.notice_emitted,0)
            finally:p.lock.close()

    def test_real_disconnect_is_not_hidden_as_syncing(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_project_updates('p',False);p.set_project_updates('p',True)
                p.disconnect('与 Codex 连接中断');p.publish()
                self.assertFalse(p.resume_snapshots);self.assertEqual(self.menu_phases(p),['unknown'])
                self.assertEqual(self.menu_phases(p,'remote::p'),['unknown'])
            finally:p.lock.close()

    def test_valid_unknown_outside_user_resume_is_still_unknown_immediately(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.states['a'].valid=False;p.publish()
                self.assertEqual(self.menu_phases(p),['unknown']);self.assertFalse(self.control(p)['syncing'])
                p.states['a'].consume(snapshot(kind='systemError',unread=True),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),['failed'])
            finally:p.lock.close()

    def test_multi_chat_project_enters_together_with_continuous_ordinals(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                c=ThreadState('c');c.consume(snapshot(),'owner');p.states['c']=c
                identities=p.metadata.identities(p.states);identities['c']=identities['a'];p.publish()
                p.set_project_updates('p',False);p.set_project_updates('p',True)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),[])
                self.assertEqual([c['index'] for c in self.control(p)['threads']],[1,2])
                self.assertEqual([c['status'] for c in self.control(p)['threads']],['approval','syncing'])
                p.states['c'].consume(snapshot(),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),['approval','running'])
                self.assertEqual([c['index'] for c in self.control(p)['threads']],[1,2])
            finally:p.lock.close()

    def test_rapid_resume_pause_does_not_resurrect_and_compact_never_invalidates_data(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_project_updates('p',False);p.set_project_updates('p',True);p.set_project_updates('p',False)
                self.assertFalse(p.resume_snapshots)
                p.states['a'].consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish()
                self.assertEqual(self.menu_phases(p),[]);self.assertFalse(self.control(p)['updatesEnabled'])
                p.set_project_updates('p',True);p.states['a'].consume(snapshot(),'owner');p.publish()
                for event in ['compact_enable','compact_disable']:
                    p.consume_ui({'event':event});self.assertTrue(p.states['a'].valid)
                    self.assertEqual(self.menu_phases(p),['running']);self.assertFalse(p.resume_snapshots)
            finally:p.lock.close()

    def test_follow_send_failure_uses_real_disconnected_state_instead_of_false_color(self):
        class Broken(Followers):
            def follow(self,tid,enabled=True,*,host_id='local'):
                if enabled:raise OSError('broken pipe')
                super().follow(tid,enabled,host_id=host_id)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                p.set_project_updates('p',False);p.ipc=Broken();p.set_project_updates('p',True)
                self.assertFalse(p.connected);self.assertFalse(p.resume_snapshots)
                self.assertEqual(self.menu_phases(p),['unknown'])
                self.assertTrue(self.control(p)['updatesEnabled'])
            finally:p.lock.close()

    def test_protocol_mismatch_exits_resume_and_shows_unknown_immediately(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=self.plugin()
            try:
                tid='12345678-1234-1234-1234-123456789abc'
                p.states[tid]=p.states.pop('a');p.states[tid].id=tid
                identities=p.metadata.identities(p.states);identities[tid]=identities.pop('a');p.registry=WatchRegistry();p.publish()
                p.ipc.acknowledge_protocol=lambda _:False
                p.set_project_updates('p',False);p.set_project_updates('p',True)
                self.assertTrue(self.control(p)['syncing'])
                p.consume_ipc(p.ipc,{'type':'broadcast','method':'thread-stream-state-changed','version':999,
                    'params':{'hostId':'local','conversationId':tid,'change':snapshot()}})
                p.publish()
                self.assertFalse(p.resume_snapshots);self.assertEqual(self.menu_phases(p),['unknown'])
                self.assertFalse(self.control(p)['syncing'])
            finally:p.lock.close()
