"""Synthetic lifecycle events and scoped SQLite metadata; no real chat mutations."""
import argparse
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_read_sync import ReadSyncFixture, IPC, TID, snapshot
from main import Plugin
from state import ThreadState, WatchRegistry, thread_key
from availability import LocalThreadAvailability


class ArchiveSyncTests(ReadSyncFixture):
    def lifecycle(self, method='thread-archived', host='local', version=None, tid=TID):
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast', 'sourceClientId':'desktop', 'method':method,
            'version':version if version is not None else (2 if method=='thread-archived' else 1),
            'params':{'hostId':host, 'conversationId':tid}})

    def stream(self, host='local', unread=True):
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast', 'sourceClientId':'owner',
            'method':'thread-stream-state-changed', 'version':11,
            'params':{'hostId':host, 'conversationId':TID, 'change':snapshot(revision=2, unread=unread)}})

    def test_archive_is_host_scoped_and_preserves_other_ids_slots_and_acks(self):
        remote=self.add_state('remote-example'); self.p.publish()
        original=copy.deepcopy(self.p.registry.entries[remote.key])
        self.p.registry.acknowledged['older-history']='prior-turn'
        self.p.ipc.following.add(('local', TID))
        self.lifecycle(); self.p.publish()
        self.assertEqual([c['id'] for c in self.chats()], [remote.key])
        self.assertEqual(self.p.registry.entries[remote.key], original)
        self.assertEqual(self.p.registry.acknowledged, {'older-history':'prior-turn'})
        self.assertEqual(self.p.ipc.calls, [('local', TID, False)])
        self.assertNotIn('title', self.p.states[TID].metadata)
        self.assertNotIn('turns', self.p.states[TID].metadata)
        self.lifecycle(host=remote.host_id); self.p.publish()
        self.assertEqual(self.chats(), [])

    def test_late_snapshot_read_and_follow_frames_cannot_resurrect_archived_chat(self):
        self.lifecycle(); self.stream(); self.read(unread=True)
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-following-changed',
            'sourceClientId':'other','params':{'hostId':'local','conversationId':TID,'following':True}})
        self.p.publish(); self.p.refresh_tracked()
        self.read(unread=True, version=999)
        self.assertEqual(self.chats(), [])
        self.assertEqual(self.p.ipc.calls, [])
        self.assertNotIn(TID, self.p.pending_unread)
        self.assertEqual(self.p.protocol_errors, set())

    def test_unarchive_requeries_fresh_state_and_does_not_replay_old_completion(self):
        self.lifecycle(); self.p.publish()
        self.lifecycle('thread-unarchived'); self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertIn(('local',TID,True), self.p.ipc.calls)
        self.stream(unread=False); self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertNotIn(TID, self.p.registry.hidden)
        self.assertEqual(self.p.registry.acknowledged, {})

    def test_unarchive_preserves_seen_turn_but_later_explicit_unread_can_rearm(self):
        self.read(); self.lifecycle(); self.p.publish()
        self.lifecycle('thread-unarchived'); self.stream(); self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertEqual(self.p.registry.acknowledged[TID], 'turn-a')
        self.read(unread=True); self.p.publish()
        self.assertEqual([c['id'] for c in self.chats()], [TID])

    def test_archive_applies_even_when_project_paused_and_restore_keeps_it_paused(self):
        self.p.paused_projects['project']={'id':'project'}
        self.lifecycle(); self.p.publish()
        self.assertNotIn(TID, self.p.registry.entries)
        self.lifecycle('thread-unarchived'); self.p.publish()
        self.assertEqual(self.p.ipc.calls, [])
        self.assertEqual(self.p.paused_projects, {'project':{'id':'project'}})

    def test_hidden_ids_and_project_context_survive_reload_without_new_followers(self):
        self.p.states[TID].metadata['cwd']='/sample/project'
        self.lifecycle(); self.p.publish()
        saved=json.loads((Path(self.tmp.name)/'slots.json').read_text())
        q=Plugin(argparse.Namespace(no_ui=True,seconds=0), lock=self.p.lock)
        q.registry=WatchRegistry(saved); q.connected=True; q.ipc=IPC(); q.metadata=self.p.metadata
        q.consume_handoff(self.p.reload_handoff())
        self.assertEqual(q.ipc.calls, [])
        self.assertEqual(q.registry.hidden[TID]['projectMetadata']['cwd'], '/sample/project')
        self.assertNotIn('title', q.registry.hidden[TID]['projectMetadata'])
        q.consume_ipc(q.ipc, {'type':'broadcast','method':'thread-stream-state-changed','version':11,
            'sourceClientId':'owner','params':{'hostId':'local','conversationId':TID,'change':snapshot()}})
        q.publish(); self.assertEqual(q.last_status['projects'], [])

    def test_unknown_lifecycle_version_and_malformed_payload_do_not_hide_any_chat(self):
        self.lifecycle(version=999); self.p.publish()
        self.assertEqual(len(self.chats()), 1)
        self.assertEqual(self.p.last_status['health']['status'], 'protocol-error')
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-archived','version':2,'params':None})
        self.assertNotIn(TID, self.p.registry.hidden)

    def test_out_of_scope_archive_or_unarchive_does_not_discover_history(self):
        other='22222222-2222-4222-8222-222222222222'
        self.lifecycle(tid=other); self.lifecycle('thread-unarchived',tid=other)
        self.assertNotIn(other, self.p.registry.hidden)
        self.assertNotIn(other, self.p.states)
        self.assertEqual(self.p.ipc.calls, [])

    def test_archive_forgets_pending_notification_and_disarms_old_notice_click(self):
        self.p.pending_notice={'chat':{'id':TID}}
        self.p.notice_target=('notice', TID)
        self.p.pending_unread.add(TID); self.p.resume_snapshots[TID]=999999999
        self.lifecycle()
        self.assertIsNone(self.p.pending_notice)
        self.assertIsNone(self.p.notice_target)
        self.assertNotIn(TID, self.p.notices.phases)
        self.assertNotIn(TID, self.p.resume_snapshots)

    def test_scoped_index_cleans_legacy_deleted_local_but_never_a_remote_id(self):
        remote=self.add_state('remote-example'); self.p.publish()
        path=Path(self.tmp.name)/'state.sqlite'
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, archived INTEGER)')
        self.p.availability=LocalThreadAvailability(path)
        self.p.reconcile_availability(); self.p.publish()
        self.assertEqual([c['id'] for c in self.chats()], [remote.key])
        self.assertEqual(self.p.registry.hidden[TID]['reason'], 'deleted')
        self.assertNotIn(remote.key, self.p.registry.hidden)

    def test_local_index_archive_and_restore_request_fresh_state_without_replaying(self):
        path=Path(self.tmp.name)/'state.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, archived INTEGER)')
            db.execute('INSERT INTO threads VALUES (?,1)',(TID,))
        self.p.availability=LocalThreadAvailability(path)
        self.p.reconcile_availability(); self.p.publish()
        self.assertEqual(self.chats(), [])
        with sqlite3.connect(path) as db:db.execute('UPDATE threads SET archived=0 WHERE id=?',(TID,))
        self.p.reconcile_availability(); self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertIn(('local',TID,True),self.p.ipc.calls)
        self.stream(unread=False); self.p.publish()
        self.assertEqual(self.chats(), [])


class LocalAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'state.sqlite'
        with sqlite3.connect(self.path) as db:db.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, archived INTEGER)')
        self.reader=LocalThreadAvailability(self.path)
        self.state=ThreadState(TID); self.state.consume(snapshot(phase='inProgress'),'owner')

    def tearDown(self):self.tmp.cleanup()

    def test_new_unstored_active_chat_is_not_deleted_but_confirmed_row_deletion_is(self):
        states={TID:self.state}
        self.assertEqual(self.reader.poll(states, {}, {}), {})
        with sqlite3.connect(self.path) as db:db.execute('INSERT INTO threads VALUES (?,0)',(TID,))
        self.assertEqual(self.reader.poll(states, {}, {}), {TID:'active'})
        with sqlite3.connect(self.path) as db:db.execute('DELETE FROM threads WHERE id=?',(TID,))
        self.assertEqual(self.reader.poll(states, {}, {}), {TID:'deleted'})

    def test_archive_and_unarchive_rows_are_read_without_writing_or_enumerating_other_ids(self):
        with sqlite3.connect(self.path) as db:
            db.executemany('INSERT INTO threads VALUES (?,1)', [(TID,),('unobserved',)])
        self.assertEqual(self.reader.poll({TID:self.state}, {}, {}), {TID:'archived'})
        with sqlite3.connect(self.path) as db:db.execute('UPDATE threads SET archived=0 WHERE id=?',(TID,))
        self.assertEqual(self.reader.poll({TID:self.state}, {}, {}), {TID:'active'})
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT count(*) FROM threads').fetchone()[0], 2)

    def test_remote_cloud_and_ephemeral_chats_are_not_local_deletions(self):
        remote=ThreadState(TID,host_id='remote-example')
        self.state.metadata['threadSource']='aeon'
        ephemeral=ThreadState('22222222-2222-4222-8222-222222222222',metadata={'ephemeral':True})
        self.assertEqual(self.reader.poll({TID:self.state,remote.key:remote,ephemeral.key:ephemeral}, {}, {}), {})

    def test_missing_locked_or_incompatible_database_is_unknown_not_deleted(self):
        entries={TID:{'phase':'stopped'}}
        missing=LocalThreadAvailability(self.path.with_name('missing.sqlite'))
        self.assertEqual(missing.poll({}, entries, {}), {})
        self.assertFalse(missing.path.exists())
        with patch('availability.sqlite3.connect',side_effect=sqlite3.OperationalError('locked')):
            self.assertEqual(self.reader.poll({}, entries, {}), {})
            self.assertFalse(self.reader.available)
