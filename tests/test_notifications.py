import argparse
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from main import Plugin
from notifications import NoticeTracker
from state import ThreadState, WatchRegistry
from control import enqueue
from test_state import snapshot

PROJECT = {'id':'p','name':'真实项目 {n}','markerType':'icon','marker':'folder'}


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.state=ThreadState('a');self.state.consume(snapshot(),'owner')
        self.states={'a':self.state};self.identities={'a':PROJECT}
        self.registry=WatchRegistry();self.tracker=NoticeTracker()

    def observe(self, connected=True, language='zh-CN'):
        groups=self.registry.update(self.states,self.identities,connected,language=language)
        return self.tracker.observe(self.states,groups,connected,language,identities=self.identities)

    def test_first_snapshot_is_baseline_then_each_real_phase_edge_notifies(self):
        self.assertIsNone(self.observe())
        for flags,expected in [(['waitingOnApproval'],'approval'),(['waitingOnUserInput'],'input'),([], 'running')]:
            self.state.consume(snapshot(flags=flags),'owner')
            event=self.observe()
            self.assertEqual(event['chat']['status'],expected)
            self.assertEqual(event['chat']['id'],'a')
            self.assertEqual(event['project']['name'],'真实项目 {n}')
            self.assertEqual(event['source'],'automatic')
            self.assertIsNone(self.observe())

    def test_seeded_reload_does_not_replay_same_status(self):
        self.registry.update(self.states,self.identities,True)
        self.tracker.seed(self.registry.entries)
        self.assertIsNone(self.observe())
        self.state.consume(snapshot(flags=['waitingOnApproval']),'owner')
        self.assertEqual(self.observe()['chat']['status'],'approval')

    def test_title_locale_and_ordinal_changes_are_not_task_changes(self):
        self.observe();self.state.metadata['title']='原始标题 {n}'
        self.registry.entries['a']['index']=9
        self.identities['a']={**PROJECT,'name':'改名项目'}
        self.assertIsNone(self.observe(language='en'))
        self.assertEqual(self.registry.entries['a']['index'],9)

    def test_transport_gaps_do_not_fabricate_or_repeat_edges(self):
        self.observe();self.state.valid=False
        self.assertIsNone(self.observe(False));self.assertIsNone(self.observe())
        self.state.consume(snapshot(),'owner');self.assertIsNone(self.observe())
        self.state.consume(snapshot(flags=['waitingOnApproval']),'owner')
        self.assertEqual(self.observe()['chat']['status'],'approval')

    def test_viewed_terminal_after_idle_gap_still_has_its_subject(self):
        for gap_status,expected_phase in [('inProgress','unknown'), ('','idle')]:
            with self.subTest(gap_status=gap_status):
                self.setUp();self.observe()
                self.state.consume(snapshot('idle',False,gap_status),'owner')
                self.assertIsNone(self.observe())
                self.assertEqual(self.state.phase(),expected_phase)
                self.assertEqual(bool(self.registry.entries),expected_phase == 'unknown')
                self.state.consume(snapshot('idle',False,'completed'),'owner')
                event=self.observe(language='en')
                self.assertEqual(event['chat']['status'],'completed')
                self.assertEqual(event['chat']['detail'],'Completed')
                self.assertEqual(event['chat']['id'],'a')
                self.assertFalse(self.registry.entries)
                self.assertIsNone(self.observe())

    def test_terminal_edges_alert_even_when_codex_already_considers_them_read(self):
        for turn_status,phase in [('completed','completed'),('failed','failed'),('interrupted','stopped')]:
            for unread in [True,False]:
                with self.subTest(turn_status=turn_status,unread=unread):
                    self.setUp();self.observe()
                    self.state.consume(snapshot('idle',unread,turn_status),'owner')
                    event=self.observe()
                    self.assertEqual(event['chat']['status'],phase)
                    self.assertEqual(event['chat']['id'],'a')
                    self.assertEqual(bool(self.registry.entries),unread)
                    self.assertIsNone(self.observe())

    def test_children_and_ephemeral_chats_never_alert(self):
        for field,value in [('parentThreadId','parent'),('ephemeral',True)]:
            self.setUp();self.observe();self.state.metadata[field]=value
            self.state.metadata['threadRuntimeStatus']['activeFlags']=['waitingOnApproval']
            self.assertIsNone(self.observe())

    def test_concurrent_changes_coalesce_and_reset_drops_old_baseline(self):
        b=ThreadState('remote::b');b.consume(snapshot(),'owner')
        self.states['remote::b']=b;self.identities['remote::b']={**PROJECT,'id':'remote::p'}
        self.observe()
        for s in self.states.values():s.consume(snapshot(flags=['waitingOnApproval']),'owner')
        event=self.observe();self.assertEqual(event['chat']['id'],'remote::b')
        self.tracker.reset();self.assertIsNone(self.observe())

    def test_pipeline_writes_state_then_once_only_ephemeral_notice(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                p.connected=True;p.ui_ready=True;p.states=self.states
                p.metadata=types.SimpleNamespace(identities=lambda _:self.identities)
                output=io.StringIO();p.renderer=types.SimpleNamespace(stdin=output,poll=lambda:None)
                p.registry.acknowledged['old']='turn-7'
                p.publish();self.assertNotIn('status_notice',output.getvalue())
                output.seek(0);output.truncate(0)
                self.state.consume(snapshot(flags=['waitingOnApproval']),'owner');p.publish();p.publish()
                lines=[json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual([v['kind'] for v in lines],['state','status_notice'])
                self.assertEqual(lines[1]['notice']['chat']['id'],'a')
                saved=json.loads((Path(tmp)/'slots.json').read_text())
                self.assertEqual(saved['acknowledged'],{'old':'turn-7'})
                self.assertNotIn('notice',saved)
                self.assertEqual(p.notice_emitted,1)
            finally:p.lock.close()

    def test_private_sample_has_no_real_chat_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp,'CODEX_MENU_STATUS_CAPTURE':'1'}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                p.ui_ready=True;output=io.StringIO();p.renderer=types.SimpleNamespace(stdin=output,poll=lambda:None)
                before=copy.deepcopy(p.registry.saved());ticket=enqueue(p.data,'notice-demo');p.consume_commands()
                command=json.loads(output.getvalue())
                self.assertEqual(command['notice']['source'],'diagnostic')
                self.assertEqual(command['notice']['id'],'diagnostic-'+ticket)
                self.assertEqual(p.registry.saved(),before)
                self.assertFalse(p.states);self.assertEqual(p.notice_emitted,0)
                self.assertFalse((p.data/'settings.json').exists())
            finally:p.lock.close()

    def test_notice_click_opens_an_already_read_chat_without_readding_or_marking_it(self):
        tid='11111111-1111-4111-8111-111111111111'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                p.renderer=types.SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
                before=copy.deepcopy(p.registry.saved())
                self.assertTrue(p.emit_notice({'id':'notice-a','source':'automatic','chat':{'id':tid}}))
                with patch('main.sys.platform','darwin'), patch('main.subprocess.Popen') as opened:
                    p.consume_ui({'event':'notice_open','noticeId':'notice-a','threadId':tid})
                    p.consume_ui({'event':'notice_open','noticeId':'notice-a','threadId':tid})
                    opened.assert_called_once()
                    self.assertEqual(opened.call_args.args[0],['/usr/bin/open','codex://threads/'+tid])
                self.assertEqual(p.notice_receipts['opened'],1)
                self.assertEqual(p.registry.saved(),before)
                self.assertFalse(p.states)
            finally:p.lock.close()

    def test_stale_close_and_mismatched_notice_click_cannot_open_a_different_remote_chat(self):
        tid='host name::11111111-1111-4111-8111-111111111111'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                p.renderer=types.SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
                p.emit_notice({'id':'a','source':'automatic','chat':{'id':tid}})
                p.emit_notice({'id':'b','source':'automatic','chat':{'id':tid}})
                with patch('main.sys.platform','darwin'), patch('main.subprocess.Popen') as opened:
                    p.consume_ui({'event':'notice_closed','noticeId':'a','source':'automatic','reason':'replaced'})
                    p.consume_ui({'event':'notice_open','noticeId':'a','threadId':tid})
                    p.consume_ui({'event':'notice_open','noticeId':'b','threadId':'11111111-1111-4111-8111-111111111111'})
                    opened.assert_not_called()
                    p.consume_ui({'event':'notice_open','noticeId':'b','threadId':tid})
                    self.assertEqual(opened.call_args.args[0],['/usr/bin/open','codex://threads/11111111-1111-4111-8111-111111111111?hostId=host+name'])
            finally:p.lock.close()

    def test_expired_closed_sample_and_disabled_notices_have_no_open_capability(self):
        tid='11111111-1111-4111-8111-111111111111'
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_MENU_STATUS_DATA':tmp}):
            p=Plugin(argparse.Namespace(no_ui=True,seconds=0))
            try:
                p.renderer=types.SimpleNamespace(stdin=io.StringIO(),poll=lambda:None)
                for reason in ['manual','expired']:
                    p.emit_notice({'id':reason,'source':'automatic','chat':{'id':tid}})
                    p.consume_ui({'event':'notice_closed','noticeId':reason,'source':'automatic','reason':reason})
                    with patch('main.sys.platform','darwin'), patch('main.subprocess.Popen') as opened:
                        p.consume_ui({'event':'notice_open','noticeId':reason,'threadId':tid});opened.assert_not_called()
                for source,enabled in [('diagnostic',True),('automatic',False)]:
                    p.enabled=enabled
                    p.emit_notice({'id':'n','source':source,'chat':{'id':tid}})
                    with patch('main.sys.platform','darwin'), patch('main.subprocess.Popen') as opened:
                        p.consume_ui({'event':'notice_open','noticeId':'n','threadId':tid});opened.assert_not_called()
                self.assertEqual(p.notice_receipts['opened'],0)
            finally:p.lock.close()
