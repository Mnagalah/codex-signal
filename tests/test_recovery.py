"""Recovery without restarting Codex: fake owners, temporary identities, no tasks."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_read_sync import ReadSyncFixture, IPC, TID, snapshot
from main import Plugin
from recovery import Recovery
from state import ThreadState, thread_key

REMOTE = 'remote-control:example'
OTHER = '22222222-2222-4222-8222-222222222222'


class RecoveryTests(ReadSyncFixture):
    def lifecycle(self, status, client='owner', client_type='desktop-window', version=0):
        self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'method': 'client-status-changed',
            'version': version, 'params': {'clientId': client, 'clientType': client_type, 'status': status}})

    def stream(self, host='local', owner='new-owner', unread=True, phase='inProgress', tid=TID):
        self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'method': 'thread-stream-state-changed',
            'sourceClientId': owner, 'version': 11, 'params': {'hostId': host,
            'conversationId': tid, 'change': snapshot(unread=unread, phase=phase, revision=2)}})

    @staticmethod
    def initialize(p):
        ipc = IPC()
        ipc.close = lambda: None
        ipc.acknowledge_protocol = lambda message: message.get('method') == 'initialize'
        p.ipc = ipc
        p.consume_ipc(ipc, {'type': 'response', 'method': 'initialize'})
        return ipc

    def test_logical_reset_drops_only_observer_transport_and_requires_new_session(self):
        remote = self.add_state(REMOTE)
        self.p.publish()
        saved = copy.deepcopy(self.p.registry.saved())
        ipc = self.p.ipc
        closed = []
        ipc.close = lambda: closed.append(True)
        self.p.consume_ipc(ipc, {'type': 'broadcast', 'method': 'ipc-connection-reset',
            'version': 1, 'params': {}})
        self.assertEqual(closed, [True])
        self.assertFalse(self.p.connected)
        self.assertEqual(self.p.retry_at, 0)
        self.assertTrue(all(not s.valid for s in self.p.states.values()))
        self.assertEqual(self.p.registry.saved(), saved)
        replacement = self.initialize(self.p)
        self.assertEqual(set(replacement.calls), {('local', TID, True), (REMOTE, TID, True)})
        # Old socket callbacks cannot restore freshness in the new session.
        self.p.consume_ipc(ipc, {'type':'broadcast','method':'thread-stream-state-changed',
            'version':11,'sourceClientId':'owner','params':{'hostId':REMOTE,
            'conversationId':TID,'change':snapshot()}})
        self.assertFalse(remote.valid)

    def test_reconnect_refollows_inactive_remote_not_just_visible_registry(self):
        remote = self.add_state(REMOTE)
        remote.metadata['hasUnreadTurn'] = False
        self.p.publish()
        self.assertNotIn(remote.key, self.p.registry.entries)
        ipc = self.initialize(self.p)
        self.assertIn((REMOTE, TID, True), ipc.calls)
        self.assertIn(('local', TID, True), ipc.calls)

    def test_owner_loss_invalidates_only_that_owner_and_rejects_late_frames(self):
        remote = self.add_state(REMOTE)
        remote.owner = 'other-owner'
        self.p.publish()
        old = copy.deepcopy(self.p.registry.entries[TID])
        self.lifecycle('disconnected')
        self.assertFalse(self.p.states[TID].valid)
        self.assertTrue(remote.valid)
        self.stream(owner='owner')
        self.assertFalse(self.p.states[TID].valid)
        self.lifecycle('connected', client='new-owner')
        self.stream()
        self.p.publish()
        self.assertTrue(self.p.states[TID].valid)
        self.assertEqual(self.p.states[TID].owner, 'new-owner')
        for field in ('id', 'index', 'firstSeen'):
            self.assertEqual(old[field], self.p.registry.entries[TID][field])
        self.assertEqual(self.p.notice_emitted, 0)

    def test_owner_reconnect_reannounces_even_if_following_set_is_already_populated(self):
        self.p.ipc.following.add(('local', TID))
        self.lifecycle('connected', client='replacement-owner')
        self.assertIn(('local', TID, True), self.p.ipc.calls)

    def test_other_signal_observers_do_not_cause_follow_storm(self):
        self.lifecycle('connected', client='another-signal', client_type='codex-menu-status-plugin')
        self.assertEqual(self.p.ipc.calls, [])

    def test_lifecycle_version_is_checked_and_valid_event_clears_only_its_error(self):
        self.lifecycle('connected', version=9)
        self.assertIn(('*', 'connection'), self.p.protocol_errors)
        self.lifecycle('connected')
        self.assertNotIn(('*', 'connection'), self.p.protocol_errors)

    def test_cold_process_restores_inactive_identity_but_not_turn_owner_or_phase(self):
        remote = self.add_state(REMOTE)
        remote.metadata.update(hasUnreadTurn=False, cwd='/sample/project')
        self.p.recovery.remember(remote.key, remote.metadata)
        self.p.publish()
        q = Plugin(self.p.args, lock=self.p.lock)
        q.metadata = self.p.metadata
        q.metadata.poll = lambda: (False, False)
        with patch('main.latest_release', return_value=Path(__import__('main').ROOT)):
            q.elect()
        self.assertIn(remote.key, q.states)
        self.assertFalse(q.states[remote.key].valid)
        self.assertIsNone(q.states[remote.key].owner)
        self.assertEqual(q.states[remote.key].metadata['cwd'], '/sample/project')
        self.assertNotIn('turns', q.states[remote.key].metadata)
        ipc = self.initialize(q)
        self.assertIn((REMOTE, TID, True), ipc.calls)

    def test_new_local_and_remote_presence_replay_discovers_without_history_scan(self):
        self.p.states.clear()
        self.p.registry.entries.clear()
        for host in ('local', REMOTE):
            self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-following-changed',
                'sourceClientId':'desktop','version':1,'params':{'hostId':host,
                    'conversationId':OTHER,'following':True}})
        self.assertEqual(set(self.p.ipc.calls), {('local', OTHER, True), (REMOTE, OTHER, True)})
        for host in ('local', REMOTE):
            self.stream(host=host, tid=OTHER)
        self.p.publish()
        self.assertEqual(set(c['id'] for c in self.chats()), {OTHER, thread_key(REMOTE, OTHER)})

    def test_health_is_not_ready_until_required_snapshots_are_fresh(self):
        self.p.states[TID].valid = False
        with patch('main.time.monotonic', return_value=100):
            self.p.expect_snapshot(TID, baseline=True)
            self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'syncing')
        with patch('main.time.monotonic', return_value=106):
            self.p.publish()
        self.assertTrue(self.p.connected)
        self.assertEqual(self.p.last_status['health']['status'], 'unavailable')
        self.assertEqual(self.chats()[0]['status'], 'unknown')
        self.stream(phase='completed', unread=False)
        self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'ready')
        self.assertEqual(self.chats(), [])
        self.assertEqual(self.p.notice_emitted, 0)

    def test_first_recovered_snapshot_is_baseline_then_real_transition_notifies(self):
        self.lifecycle('disconnected')
        self.stream(owner='new-owner')
        self.p.publish()
        self.assertEqual(self.p.notice_emitted, 0)
        self.stream(owner='new-owner', phase='completed')
        self.p.publish()
        self.assertEqual(self.p.notice_emitted, 1)

    def test_project_and_master_pause_cancel_retry_without_changing_saved_ids(self):
        remote = self.add_state(REMOTE)
        self.p.publish()
        self.p.expect_snapshot(TID, baseline=True)
        self.p.expect_snapshot(remote.key, baseline=True)
        self.p.set_project_updates('project', False)
        self.assertNotIn(TID, self.p.recovery.pending)
        self.assertIn(remote.key, self.p.recovery.pending)
        saved = copy.deepcopy(self.p.registry.saved())
        self.p.ipc.close = lambda: None
        self.p.control('disable')
        self.assertFalse(self.p.recovery.pending)
        self.assertEqual(self.p.registry.saved(), saved)

    def test_archive_cancels_recovery_and_retired_ids_never_refollow(self):
        self.p.expect_snapshot(TID)
        self.p.hide_thread(TID, 'archived')
        self.assertNotIn(TID, self.p.recovery.pending)
        self.lifecycle('connected', client='new-owner')
        self.assertEqual(self.p.ipc.calls, [])

    def test_restart_hints_keep_no_titles_tasks_owners_or_transcript(self):
        self.p.publish()
        value = json.loads((Path(self.tmp.name)/'recovery.json').read_text())
        record = value['threads'][TID]
        self.assertEqual(set(record), {'lastSeen', 'projectMetadata'})
        self.assertTrue(set(record['projectMetadata']) <= {'workspaceKind','cwd','projectId'})
        self.assertNotIn('Sample chat', json.dumps(value))

    def test_missing_initialize_response_times_out_without_touching_task_records(self):
        p = self.p
        p.connected = False
        p.handshake_deadline = 100
        p.ipc.close = lambda: None
        p.primary = True
        p.metadata.poll = lambda: (False, False)
        p.events.put(('shutdown', None))
        with patch('main.time.monotonic', return_value=106), patch('main.signal.signal'):
            p.run(start_mcp_reader=False)
        self.assertFalse(p.connected)
        self.assertIsNone(p.ipc)
        self.assertEqual(p.last_status['health']['status'], 'disconnected')
        self.assertIn(TID, p.registry.entries)

    def test_unavailable_recent_hint_does_not_claim_an_inactive_chat_is_running(self):
        self.read()
        self.p.states[TID].valid = False
        self.p.expect_snapshot(TID, baseline=True)
        self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertFalse(self.p.recovery.pending[TID].required)
        self.assertEqual(self.p.last_status['health']['status'], 'ready')


class RetryTests(unittest.TestCase):
    def test_retry_is_coalesced_backed_off_and_continues_after_five_second_ui_timeout(self):
        r = Recovery()
        r.expect(TID, required=True, baseline=True, now=0)
        for _ in range(20): r.expect(TID, now=0)
        self.assertEqual(r.due(now=0), [TID])
        self.assertEqual(r.due(now=.9), [])
        self.assertEqual(r.due(now=1), [TID])
        self.assertEqual(r.due(now=3), [TID])
        self.assertEqual(r.health(now=6), 'unavailable')
        self.assertEqual(r.due(now=7), [TID])
        self.assertTrue(r.received(TID))
        self.assertEqual(r.due(now=100), [])
        self.assertIsNone(r.health(now=100))

    def test_batches_are_bounded_and_paused_or_archived_keys_can_be_cancelled(self):
        r = Recovery()
        for n in range(30): r.expect(str(n), now=0)
        self.assertEqual(len(r.due(now=0)), 8)
        r.cancel(set(r.pending))
        self.assertEqual(r.due(now=1), [])

    def test_recent_limit_preserves_visible_identity_and_never_saves_task_state(self):
        r = Recovery()
        for n in range(140): r.remember(str(n), {'title':'discard', 'cwd':'/sample', 'turns':[1]})
        saved = r.saved(visible={'0'}, hidden={'1'})
        self.assertEqual(len(saved['threads']), 129)
        self.assertIn('0', saved['threads'])
        self.assertNotIn('1', saved['threads'])
        self.assertTrue(all(set(record['projectMetadata']) == {'cwd'} for record in saved['threads'].values()))

    def test_malformed_or_non_uuid_hints_are_not_discovery_candidates(self):
        r = Recovery()
        r.load({'threads': None})
        r.load({'threads': {'bad': {'lastSeen': 1}, TID: {'lastSeen': 1, 'projectMetadata': None}}})
        self.assertEqual(set(r.recent), {TID})
        self.assertEqual(r.recent[TID]['projectMetadata'], {})
