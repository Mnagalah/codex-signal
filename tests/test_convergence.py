"""Synthetic regressions for the convergence audit; never contact the desktop."""
import argparse
import gc
import importlib.util
import json
from pathlib import Path
import queue
import sys
import types
from unittest.mock import patch

from test_read_sync import ReadSyncFixture, IPC, TID, snapshot
from main import Plugin, ROOT, load_plugin_class
from lifecycle import PREFIX
from state import ThreadState, thread_key


class ConvergenceTests(ReadSyncFixture):
    def test_explicit_unread_rearms_only_the_current_host_and_turn(self):
        remote = self.add_state('remote-control:example-host')
        self.p.registry.acknowledged['other-history'] = 'other-turn'
        for host in ('local', remote.host_id):
            with self.subTest(host=host):
                key = thread_key(host, TID)
                self.read(host); self.p.publish()
                self.assertNotIn(key, [c['id'] for c in self.chats()])
                self.read(host, unread=True); self.p.publish()
                self.assertIn(key, [c['id'] for c in self.chats()])
                self.assertNotIn(key, self.p.registry.acknowledged)
                self.read(host); self.p.publish()
                self.assertNotIn(key, [c['id'] for c in self.chats()])
        self.assertEqual(self.p.registry.acknowledged['other-history'], 'other-turn')
        self.assertEqual(self.p.ipc.calls, [])

    def test_protocol_health_is_visible_without_any_prior_entry_and_recovers(self):
        self.p.states.clear(); self.p.registry.entries.clear()
        message = {'type':'broadcast','method':'thread-stream-state-changed','sourceClientId':'owner',
                   'version':999,'params':{'hostId':'local','conversationId':TID,'change':snapshot()}}
        self.p.consume_ipc(self.p.ipc, message); self.p.publish()
        self.assertTrue(self.p.last_status['connected'])  # Transport is distinct.
        self.assertEqual(self.chats(), [])
        self.assertEqual(self.p.last_status['health']['status'], 'protocol-error')
        self.assertIn('protocol changed', self.p.last_status['health']['detail'])
        message['version'] = 11
        self.p.consume_ipc(self.p.ipc, message); self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'ready')
        self.assertNotIn('protocol changed', self.p.last_status['health']['detail'])

    def test_read_protocol_health_is_not_cleared_by_a_stream_snapshot(self):
        self.read(version=999)
        self.p.states[TID].consume(snapshot(revision=2), 'owner')
        self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'protocol-error')
        self.read(unread=True); self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'ready')

    def test_changed_protocol_shape_is_an_explicit_health_error_not_a_crash(self):
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-state-changed','version':999,'params':None})
        self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'protocol-error')
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-state-changed','sourceClientId':'owner','version':11,
            'params':{'hostId':'local','conversationId':TID,'change':snapshot(revision=2)}})
        self.p.publish()
        self.assertEqual(self.p.last_status['health']['status'], 'ready')

    def test_reload_queue_hands_off_read_remote_without_replaying_turn_state(self):
        remote = self.add_state('remote-control:example-host')
        remote.metadata.update(hasUnreadTurn=False, workspaceKind='project', cwd='/sample/project')
        self.p.publish()
        self.p.control('reload')
        kind, observed = self.p.events.get_nowait()
        self.assertEqual(kind, 'payload_handoff')
        self.assertTrue(all(set(item['projectMetadata']) <= {'workspaceKind','cwd','projectId'} for item in observed))
        q = Plugin(self.p.args, events=self.p.events, lock=self.p.lock)
        q.ipc = IPC(); q.connected = True; q.metadata = self.p.metadata
        q.registry = self.p.registry
        q.consume_handoff(observed)
        self.assertIn((remote.host_id, TID, True), q.ipc.calls)
        restored = q.states[remote.key]
        self.assertFalse(restored.valid)
        self.assertEqual(restored.latest_turn, {})
        self.assertNotIn('hasUnreadTurn', restored.metadata)
        q.consume_ipc(q.ipc, {'type':'broadcast','method':'thread-stream-state-changed','sourceClientId':'owner','version':11,
            'params':{'hostId':remote.host_id,'conversationId':TID,'change':snapshot(revision=2)}})
        q.publish()
        self.assertIn(remote.key, [c['id'] for p in q.last_status['projects'] for c in p['threads']])

    def test_handoff_event_runs_through_the_real_replacement_loop(self):
        remote = self.add_state('remote-control:example-host')
        remote.metadata['hasUnreadTurn'] = False
        self.p.publish(); self.p.control('reload')
        q = Plugin(self.p.args, events=self.p.events, lock=self.p.lock)
        q.connected = True; q.ipc = IPC(); q.ipc.close = lambda: None
        q.metadata = types.SimpleNamespace(identities=self.p.metadata.identities, poll=lambda: (False, False))
        q.events.put(('shutdown', None))
        with patch('main.signal.signal'):
            q.run(start_mcp_reader=False)
        self.assertIn(remote.key, q.states)
        self.assertIn((remote.host_id, TID, True), q.ipc.calls)
        self.assertFalse(q.states[remote.key].valid)

    def test_handoff_before_initialize_retains_pending_ids_and_paused_scope(self):
        remote = self.add_state('remote-control:example-host')
        remote.metadata['hasUnreadTurn'] = False
        self.p.publish()
        observed = self.p.reload_handoff()
        q = Plugin(self.p.args, lock=self.p.lock)
        q.metadata = self.p.metadata
        q.paused_projects = {thread_key(remote.host_id, 'project'): {}}
        q.consume_handoff(observed)
        self.assertIn(remote.key, q.pending_discovery)
        self.assertTrue(q.project_paused(remote.key))
        q.connected = True; q.ipc = IPC()
        q.consume_handoff(observed)
        self.assertEqual(q.ipc.calls, [('local', TID, True)])

    def test_unread_edge_before_fresh_snapshot_rearms_the_restored_turn(self):
        self.read(); self.p.publish()
        self.p.states[TID].valid = False
        self.read(unread=True)
        self.assertIn(TID, self.p.pending_unread)
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-state-changed','sourceClientId':'owner','version':11,
            'params':{'hostId':'local','conversationId':TID,'change':snapshot(revision=2)}})
        self.p.publish()
        self.assertEqual(len(self.chats()), 1)
        self.assertNotIn(TID, self.p.pending_unread)

    def test_paused_unread_intent_does_not_mutate_records_until_fresh_resume(self):
        self.read(); self.p.publish()
        self.p.paused_projects['project'] = {'id':'project'}
        saved = json.loads(json.dumps(self.p.registry.saved()))
        self.read(unread=True)
        self.assertEqual(self.p.registry.saved(), saved)
        self.p.paused_projects.clear()
        self.p.consume_ipc(self.p.ipc, {'type':'broadcast','method':'thread-stream-state-changed','sourceClientId':'owner','version':11,
            'params':{'hostId':'local','conversationId':TID,'change':snapshot(revision=2)}})
        self.p.publish()
        self.assertEqual(len(self.chats()), 1)

    def test_same_installed_version_reuses_its_factory(self):
        cls = load_plugin_class(ROOT)
        for _ in range(20):
            self.assertIs(load_plugin_class(ROOT), cls)
        packages = [k for k in sys.modules if k.startswith(PREFIX) and '.' not in k]
        self.assertLessEqual(len(packages), 1)

    def test_legacy_host_timestamp_namespaces_are_pruned_on_payload_init(self):
        # Old installed hosts retain their original loader function. New
        # payloads must also bound those namespaces without replacing the host.
        for n in range(20):
            name = PREFIX + 'legacy_' + str(n)
            package = types.ModuleType(name); package.__path__ = [str(ROOT / 'server')]
            sys.modules[name] = package
            spec = importlib.util.spec_from_file_location(name + '.main', ROOT / 'server/main.py')
            module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            instance = module.Plugin(self.p.args, lock=self.p.lock)
        gc.collect()
        packages = [k for k in sys.modules if k.startswith(PREFIX) and '.' not in k]
        self.assertEqual(packages, [name])
        self.assertEqual(instance.registry.acknowledged, {})
