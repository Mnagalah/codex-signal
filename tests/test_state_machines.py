"""Reachable state-machine interleavings using private, fictional fixtures."""
import copy
import io
import json
import os
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'server'))
from desktop import DesktopIPC
from state import ThreadState
from test_read_sync import ReadSyncFixture, TID, snapshot

OTHER = '22222222-2222-4222-8222-222222222222'
REMOTE = 'remote-control:example'


class StateMachineTests(ReadSyncFixture):
    def stream(self, host='local', *, owner='owner', **values):
        self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'version': 11,
            'method': 'thread-stream-state-changed', 'sourceClientId': owner,
            'params': {'hostId': host, 'conversationId': TID, 'change': snapshot(**values)}})

    def test_offline_owner_stays_fenced_after_replacement_snapshot(self):
        for host in ('local', REMOTE):
            with self.subTest(host=host):
                state = self.add_state(host)
                self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'version': 0,
                    'method': 'client-status-changed', 'params': {
                        'clientId': 'owner', 'status': 'disconnected'}})
                self.stream(host, owner='replacement', phase='inProgress', revision=10)
                self.stream(host, owner='owner', phase='completed', revision=2)
                self.assertEqual(state.owner, 'replacement')
                self.assertEqual(state.phase(), 'running')
        # An explicit reconnect, not a replacement's snapshot, clears the fence.
        self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'version': 0,
            'method': 'client-status-changed', 'params': {'clientId': 'owner', 'status': 'connected'}})
        self.stream(owner='owner', phase='inProgress', revision=11)
        self.assertEqual(self.p.states[TID].owner, 'owner')

    def test_disconnected_owner_cannot_publish_its_first_late_snapshot(self):
        self.p.consume_ipc(self.p.ipc, {'type': 'broadcast', 'version': 0,
            'method': 'client-status-changed', 'params': {
                'clientId': 'not-yet-observed', 'status': 'disconnected'}})
        self.stream(owner='not-yet-observed', phase='inProgress', revision=2)
        self.assertEqual(self.p.states[TID].owner, 'owner')

    def test_transport_failure_while_retiring_a_chat_keeps_the_retirement(self):
        self.p.ipc.following.add(('local', TID))
        self.p.ipc.close = lambda: None
        self.p.ipc.follow = lambda *a, **kw: (_ for _ in ()).throw(TimeoutError('stalled router'))
        self.p.hide_thread(TID, 'archived')
        self.assertIn(TID, self.p.registry.hidden)
        self.assertNotIn(TID, self.p.registry.entries)
        self.assertFalse(self.p.connected)

    def test_visible_chat_becoming_excluded_leaves_no_ghost_or_notice_baseline(self):
        for field, value in [('ephemeral', True), ('parentThreadId', OTHER)]:
            with self.subTest(field=field):
                state = self.p.states[TID]
                state.valid = False
                state.metadata.pop('ephemeral', None)
                state.metadata.pop('parentThreadId', None)
                state.consume(snapshot(phase='inProgress'), 'owner')
                self.p.publish()
                state.consume({'type': 'patches', 'baseRevision': 1, 'revision': 2,
                    'patches': [{'op': 'add', 'path': [field], 'value': value}]}, 'owner')
                self.p.publish()
                self.assertNotIn(TID, self.p.registry.entries)
                self.assertNotIn(TID, self.p.notices.phases)
                before = self.p.notice_emitted
                state.consume(snapshot(phase='completed', revision=3), 'owner')
                self.p.publish()
                self.assertEqual(self.p.notice_emitted, before)  # Re-entry is a baseline.

    def test_excluded_chat_cancels_undelivered_notice(self):
        state = self.p.states[TID]
        for field, value in [('ephemeral', True), ('parentThreadId', OTHER)]:
            with self.subTest(field=field):
                state.metadata.pop('ephemeral', None)
                state.metadata.pop('parentThreadId', None)
                state.metadata['threadRuntimeStatus'] = {'type': 'active', 'activeFlags': []}
                self.p.publish()
                state.metadata['threadRuntimeStatus']['activeFlags'] = ['waitingOnApproval']
                self.p.publish()
                self.assertIsNotNone(self.p.pending_notice)
                state.metadata[field] = value
                self.p.publish()
                self.assertIsNone(self.p.pending_notice)

    def test_selected_alert_is_not_lost_behind_a_simultaneous_disabled_edge(self):
        state = ThreadState(OTHER)
        state.consume(snapshot(phase='completed'), 'owner')
        self.p.states[OTHER] = state
        self.p.publish()
        self.p.notification_states = {'input'}
        self.p.states[TID].metadata['threadRuntimeStatus'] = {
            'type': 'active', 'activeFlags': ['waitingOnUserInput']}
        state.metadata['threadRuntimeStatus'] = {'type': 'active', 'activeFlags': []}
        self.p.publish()
        self.assertIsNotNone(self.p.pending_notice)
        self.assertEqual(self.p.pending_notice['chat']['id'], TID)
        self.assertEqual(self.p.pending_notice['chat']['status'], 'input')
        self.assertEqual(self.p.notices.phases[OTHER], 'running')
        self.p.pending_notice = None
        self.p.notification_states.add('running')
        self.p.publish()
        self.assertIsNone(self.p.pending_notice)  # Enabling does not replay old edges.

    def test_read_during_gap_waits_for_same_terminal_turn_on_each_host(self):
        for host in ('local', REMOTE):
            with self.subTest(host=host):
                state = self.add_state(host)
                state.valid = False
                self.read(host)
                self.assertNotIn(state.key, self.p.registry.acknowledged)
                self.stream(host, revision=2)
                self.p.publish()
                self.assertEqual(self.p.registry.acknowledged.get(state.key), 'turn-a')
                self.assertNotIn(state.key, {c['id'] for c in self.chats()})

    def test_read_during_gap_never_acknowledges_a_different_turn(self):
        self.p.states[TID].valid = False
        self.read()
        self.stream(turn='turn-b', revision=2)
        self.p.publish()
        self.assertNotIn(TID, self.p.registry.acknowledged)
        self.assertEqual(self.chats()[0]['status'], 'completed')

    def test_paused_project_read_intent_is_confirmed_on_resume(self):
        saved = copy.deepcopy(self.p.registry.saved())
        self.p.set_project_updates('project', False)
        self.read()
        self.assertEqual(self.p.registry.saved(), saved)
        self.p.set_project_updates('project', True)
        self.stream(revision=2)
        self.p.publish()
        self.assertEqual(self.chats(), [])
        self.assertEqual(self.p.registry.acknowledged.get(TID), 'turn-a')

    def test_explicit_unread_cancels_buffered_read(self):
        self.p.states[TID].valid = False
        self.read()
        self.read(unread=True)
        self.stream(revision=2)
        self.p.publish()
        self.assertEqual(self.chats()[0]['status'], 'completed')
        self.assertNotIn(TID, self.p.registry.acknowledged)

    def test_reload_preserves_only_exact_read_intent_not_a_cached_task(self):
        self.p.states[TID].valid = False
        self.read()
        handoff = self.p.reload_handoff()
        self.p.states.clear()
        self.p.consume_handoff(handoff)
        self.assertFalse(self.p.states[TID].valid)
        self.assertNotIn('turns', self.p.states[TID].metadata)
        self.stream(revision=2)
        self.p.publish()
        self.assertEqual(self.p.registry.acknowledged.get(TID), 'turn-a')


class Child:
    def __init__(self):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.returncode = None
    def poll(self): return self.returncode
    def wait(self, timeout=None): self.returncode = 0; return 0
    def terminate(self): self.returncode = -15


class RendererRecoveryTests(ReadSyncFixture):
    def test_real_service_loop_survives_launch_oserror(self):
        self.p.args.no_ui = False
        self.p.metadata.poll = lambda: (False, False)
        self.p.ipc.close = lambda: None
        self.p.events.put(('shutdown', None))
        with patch('main.subprocess.Popen', side_effect=OSError('launch failed')), \
                patch('main.latest_release', return_value=__import__('main').ROOT), \
                patch('main.signal.signal'):
            self.p.run(start_mcp_reader=False)
        self.assertTrue(self.p.primary)
        self.assertFalse(self.p.ui_ready)

    def test_real_service_loop_replaces_an_eof_renderer_without_manual_reload(self):
        old, replacement = Child(), Child()
        self.p.args.no_ui = False
        self.p.primary = True
        self.p.renderer = old
        self.p.metadata.poll = lambda: (False, False)
        self.p.ipc.close = lambda: None
        now, events = [100], [0]
        def next_event(timeout):
            events[0] += 1
            if events[0] == 1:
                old.returncode = 0
                now[0] = 101
                return 'ui_eof', old
            if events[0] == 2:
                now[0] = 102
                return 'ui_invalid', old
            return 'shutdown', None
        with patch('main.time.monotonic', side_effect=lambda: now[0]), \
                patch.object(self.p.events, 'get', side_effect=next_event), \
                patch('main.subprocess.Popen', return_value=replacement) as launch, \
                patch.object(self.p, 'start_reader'), patch('main.signal.signal'):
            self.p.run(start_mcp_reader=False)
        launch.assert_called_once()
        self.assertIs(self.p.renderer, replacement)

    def test_repeated_launch_failures_back_off_and_stable_ready_resets_attempts(self):
        self.p.args.no_ui = False
        self.p.primary = True
        with patch('main.subprocess.Popen', side_effect=OSError('launch failed')) as launch:
            for now, deadline in [(100, 101), (101, 103), (103, 107), (107, 115), (115, 131), (131, 161)]:
                self.p.ensure_renderer(now=now)
                self.assertEqual(self.p.renderer_retry_at, deadline)
                self.p.ensure_renderer(now=deadline-.1)
            self.assertEqual(launch.call_count, 6)
        child = Child()
        with patch('main.subprocess.Popen', return_value=child), patch.object(self.p, 'start_reader'):
            self.p.ensure_renderer(now=161)
        self.p.consume_ui({'event': 'ready'})
        self.p.ensure_renderer(now=171)
        self.assertEqual(self.p.renderer_failures, 0)

    def test_stale_child_callbacks_cannot_change_replacement_readiness(self):
        old, current = Child(), Child()
        self.p.renderer = current
        self.p.primary = True
        self.p.ui_ready = False
        self.p.metadata.poll = lambda: (False, False)
        self.p.ipc.close = lambda: None
        self.p.events.put(('ui', (old, {'event': 'ready', 'layoutSource': 'old', 'layoutVersion': '0', 'layoutEngine': 'old'})))
        self.p.events.put(('ui_eof', old))
        self.p.events.put(('ui', (current, {'event': 'ready', 'layoutSource': 'new', 'layoutVersion': '1', 'layoutEngine': 'new'})))
        self.p.events.put(('shutdown', None))
        with patch('main.signal.signal'):
            self.p.run(start_mcp_reader=False)
        self.assertTrue(self.p.ui_ready)
        self.assertEqual(self.p.ui_layout['source'], 'new')

    def test_nonreading_renderer_does_not_block_state_service(self):
        read_fd, write_fd = os.pipe()
        child = Child()
        child.stdin = os.fdopen(write_fd, 'w')
        self.p.renderer = child
        errors, results = [], []
        def emit():
            try:
                results.append(self.p.emit_notice({'id': 'n', 'source': 'automatic',
                    'chat': {'id': TID, 'title': 'x' * 262144}}))
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=emit, daemon=True)
        try:
            with patch('main.RENDERER_WRITE_TIMEOUT', .05, create=True):
                worker.start(); worker.join(.5)
                self.assertFalse(worker.is_alive(), 'renderer write exceeded deadline')
            self.assertFalse(errors)
            self.assertEqual(results, [False])
            self.assertFalse(self.p.ui_ready)
            self.assertTrue(self.p.running)
            self.assertTrue(self.p.connected)
        finally:
            os.close(read_fd)
            if worker.ident is not None: worker.join(1)
            child.stdin.close()

    def test_launch_failure_is_retried_without_releasing_primary_or_records(self):
        self.p.args.no_ui = False
        saved = copy.deepcopy(self.p.registry.saved())
        child = Child()
        with patch('main.subprocess.Popen', side_effect=[OSError('launch failed'), child]) as launch, \
                patch.object(self.p, 'start_reader'), patch('main.time.monotonic', return_value=100):
            self.p.primary = True
            self.p.ensure_renderer()
            self.assertFalse(self.p.ui_ready)
            self.p.ensure_renderer(now=100.5)
            self.assertEqual(launch.call_count, 1)
            self.p.ensure_renderer(now=101)
            self.assertEqual(launch.call_count, 2)
        self.assertIs(self.p.renderer, child)
        self.assertTrue(self.p.primary)
        self.assertTrue(self.p.connected)
        self.assertEqual(self.p.registry.saved(), saved)
        self.p.publish()
        self.assertEqual(json.loads(child.stdin.getvalue().splitlines()[0])['kind'], 'state')

    def test_exited_renderer_restarts_and_receives_even_an_unchanged_state(self):
        self.p.args.no_ui = False
        self.p.primary = True
        old, replacement = Child(), Child()
        self.p.renderer = old
        self.p.ui_ready = True
        old.returncode = 1
        with patch('main.subprocess.Popen', return_value=replacement), patch.object(self.p, 'start_reader'):
            self.p.ensure_renderer(now=10)
            self.assertFalse(self.p.ui_ready)
            self.p.ensure_renderer(now=11)
        self.p.publish()
        self.assertIs(self.p.renderer, replacement)
        self.assertEqual(json.loads(replacement.stdin.getvalue().splitlines()[0])['kind'], 'state')


class IPCWriteTests(unittest.TestCase):
    def test_nonreading_peer_cannot_block_the_event_loop_indefinitely(self):
        left, right = socket.socketpair()
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        left.setblocking(False)
        ipc = DesktopIPC(Path('unused'))
        ipc.socket = left
        ipc.SEND_TIMEOUT = .05
        errors = []
        def send():
            try: ipc.send({'payload': 'x' * 262144})
            except OSError as error: errors.append(error)
        writer = threading.Thread(target=send, daemon=True)
        try:
            writer.start(); writer.join(.5)
            self.assertFalse(writer.is_alive(), 'send blocked beyond its deadline')
            self.assertIsInstance(errors[0], TimeoutError)
            self.assertFalse(left.getblocking())
            self.assertTrue(ipc.write_failed)
            with self.assertRaises(ConnectionError):
                ipc.send({'retry': 'must use a new connection'})
            ipc.following.add(('local', TID))
            with patch.object(ipc, 'follow') as follow:
                ipc.close()
                follow.assert_not_called()  # Never append unfollow to a partial frame.
        finally:
            try: right.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            right.close(); writer.join(1); left.close()

    def test_idle_nonblocking_reader_waits_then_decodes_a_fragmented_frame(self):
        left, right = socket.socketpair()
        left.setblocking(False)
        ipc = DesktopIPC(Path('unused')); ipc.socket = left
        result = []
        reader = threading.Thread(target=lambda: result.extend(ipc.messages()), daemon=True)
        try:
            reader.start(); time.sleep(.02)
            self.assertTrue(reader.is_alive())
            from test_adapter import frame
            data = frame({'sample': True})
            for part in [data[:2], data[2:8], data[8:]]:
                right.sendall(part); time.sleep(.01)
            right.shutdown(socket.SHUT_WR); reader.join(1)
            self.assertFalse(reader.is_alive())
            self.assertEqual(result, [{'sample': True}])
        finally:
            right.close(); left.close(); reader.join(1)

    def test_partial_writes_preserve_complete_framing_under_backpressure(self):
        left, right = socket.socketpair()
        left.setblocking(False); right.setblocking(False)
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        sender = DesktopIPC(Path('unused')); sender.socket = left
        receiver = DesktopIPC(Path('unused')); receiver.socket = right
        messages = []
        worker = threading.Thread(target=lambda: messages.extend(receiver.messages()), daemon=True)
        value = {'sample': 'x' * 262144}
        try:
            worker.start(); sender.send(value); left.shutdown(socket.SHUT_WR)
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(messages, [value])
        finally:
            left.close(); right.close(); worker.join(1)


class CommandReceiptTests(unittest.TestCase):
    def test_claimed_request_without_receipt_is_not_reported_as_safely_queued(self):
        import argparse
        import tempfile
        import control
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            enqueue = control.enqueue
            def claimed(data, action, **values):
                ticket = enqueue(data, action, **values)
                self.assertEqual([r['id'] for r in control.pending(data)], [ticket])
                return ticket  # Crash window: no result has been written.
            args = argparse.Namespace(action='on', project_id=None)
            with patch.object(control, 'data_directory', return_value=root), \
                    patch.object(control, 'enqueue', side_effect=claimed), \
                    patch.object(control.argparse.ArgumentParser, 'parse_args', return_value=args), \
                    patch.object(control.time, 'monotonic', side_effect=[0, 7]):
                with self.assertRaises(SystemExit) as result:
                    control.main()
            self.assertIn('可能', str(result.exception))
            self.assertNotIn('请求已保留', str(result.exception))
            self.assertEqual(list((root/'commands').glob('*.json')), [])
