"""Protocol- and host-scoped replay using fictional desktop events."""
import copy

from test_read_sync import ReadSyncFixture, TID, snapshot, thread_key

REMOTE = 'remote-control:sample-host'


class StreamCompatibilityTests(ReadSyncFixture):
    def send(self, host, version, change):
        self.p.consume_ipc(self.p.ipc, {
            'type': 'broadcast',
            'method': 'thread-stream-state-changed',
            'sourceClientId': 'owner:' + host,
            'version': version,
            'params': {'hostId': host, 'conversationId': TID, 'change': change},
        })
        self.p.publish()

    def statuses(self):
        return {chat['id']: chat['status'] for chat in self.chats()}

    def start(self, host, version, revision=10):
        frame = snapshot(phase='inProgress', unread=False, revision=revision)
        # The canonical turn history and legacy turn list are both supported.
        state = frame['conversationState']
        turn = state.pop('turns')[0]
        state['turnHistory'] = {'history': {'entitiesByKey': {'turn-a': turn}}}
        self.send(host, version, frame)

    def patch(self, host, version, base, patches):
        self.send(host, version, {
            'type': 'patches', 'baseRevision': base, 'revision': base + 1,
            'patches': patches,
        })

    def test_supported_versions_on_both_hosts_keep_read_state_isolated(self):
        for local_version, remote_version in ((11, 13), (13, 11), (13, 13)):
            with self.subTest(local=local_version, remote=remote_version):
                self.p.states.clear()
                self.p.registry.entries.clear()
                self.p.registry.acknowledged.clear()
                versions = {'local': local_version, REMOTE: remote_version}
                for host, version in versions.items():
                    self.start(host, version)
                remote_key = thread_key(REMOTE, TID)
                self.assertEqual(self.statuses(), {TID: 'running', remote_key: 'running'})
                for host, version in versions.items():
                    # A discarded text patch still advances the revision.
                    self.patch(host, version, 10, [
                        {'op': 'add', 'path': ['turnHistory', 'history', 'entitiesByKey', 'turn-a', 'items'], 'value': ['discard']},
                    ])
                    self.patch(host, version, 11, [
                        {'op': 'replace', 'path': ['threadRuntimeStatus', 'activeFlags'], 'value': ['waitingOnApproval']},
                    ])
                self.assertEqual(self.statuses(), {TID: 'approval', remote_key: 'approval'})
                for host, version in versions.items():
                    self.patch(host, version, 12, [
                        {'op': 'replace', 'path': ['threadRuntimeStatus'], 'value': {'type': 'idle'}},
                        {'op': 'replace', 'path': ['turnHistory', 'history', 'entitiesByKey', 'turn-a', 'status'], 'value': 'completed'},
                        {'op': 'replace', 'path': ['hasUnreadTurn'], 'value': True},
                    ])
                self.assertEqual(self.statuses(), {TID: 'completed', remote_key: 'completed'})
                self.read('local'); self.p.publish()
                self.assertEqual(self.statuses(), {remote_key: 'completed'})
                self.read(REMOTE); self.p.publish()
                self.assertEqual(self.statuses(), {})
                self.assertEqual(self.p.registry.acknowledged, {TID: 'turn-a', remote_key: 'turn-a'})
                for host, version in versions.items():
                    # Replay of the same terminal turn must not undo a read.
                    self.send(host, version, snapshot(revision=14))
                    self.assertEqual(self.statuses(), {})
                    self.read(host, unread=True); self.p.publish()
                    self.assertEqual(self.statuses(), {thread_key(host, TID): 'completed'})
                    self.read(host); self.p.publish()
                self.assertEqual(self.p.last_status['health']['status'], 'ready')
                self.assertNotIn('discard', str(self.p.states))

    def test_v13_read_metadata_refreshes_both_hosts_without_a_read_broadcast(self):
        from pathlib import Path
        import json
        from desktop import DesktopMetadata

        path = Path(self.tmp.name) / 'desktop.json'
        path.write_text('{}')
        self.p.metadata = DesktopMetadata(path)
        self.p.metadata.poll()
        for host in ('local', REMOTE):
            self.send(host, 13, snapshot(unread=False, revision=10))
        read_bits = {'local': True, REMOTE: False}
        revision = 11

        def follow(tid, enabled=True, *, host_id='local'):
            self.assertEqual(tid, TID)
            self.assertTrue(enabled)
            self.send(host_id, 13, snapshot(unread=read_bits[host_id], revision=revision))

        self.p.ipc.follow = follow
        for step, (bits, visible) in enumerate((
            ((True, False), {TID: 'completed'}),
            ((True, True), {TID: 'completed', thread_key(REMOTE, TID): 'completed'}),
            ((False, True), {thread_key(REMOTE, TID): 'completed'}),
            ((False, False), {}),
        )):
            read_bits.update(zip(('local', REMOTE), bits))
            # Opaque buckets only trigger reconciliation; they do not supply chat IDs.
            replacement = path.with_suffix('.tmp')
            replacement.write_text(json.dumps({'thread-read-state-fixture': {'opaque': [step]}}))
            replacement.replace(path)
            self.assertTrue(self.p.metadata.poll()[1])
            self.p.refresh_tracked()
            self.assertEqual(self.statuses(), visible)
            revision += 1
        self.assertEqual(self.p.last_status['health']['status'], 'ready')


    def test_unrecognized_versions_cannot_mutate_payload_or_cross_host(self):
        self.start('local', 11)
        self.start(REMOTE, 13)
        remote_key = thread_key(REMOTE, TID)
        before = copy.deepcopy(self.p.states[remote_key].metadata)
        for version in (12, 14, 999, '13', 13.0, None, []):
            with self.subTest(version=version):
                self.send(REMOTE, version, snapshot(revision=999))
                self.assertEqual(self.p.states[remote_key].metadata, before)
                self.assertEqual(self.p.states[remote_key].revision, 10)
                self.assertEqual(self.statuses(), {TID: 'running', remote_key: 'unknown'})
                self.assertEqual(self.p.last_status['health']['status'], 'protocol-error')
        self.send(REMOTE, 13, snapshot(revision=11))
        self.assertEqual(self.statuses(), {TID: 'running', remote_key: 'completed'})
        self.assertEqual(self.p.last_status['health']['status'], 'ready')

    def test_v13_patch_requires_fresh_snapshot_and_same_revision_chain(self):
        self.start(REMOTE, 13)
        remote_key = thread_key(REMOTE, TID)
        self.patch(REMOTE, 13, 9, [])
        self.assertFalse(self.p.states[remote_key].valid)
        self.assertEqual(self.statuses()[remote_key], 'unknown')
        self.patch(REMOTE, 13, 10, [])
        self.assertFalse(self.p.states[remote_key].valid)
        self.start(REMOTE, 13, revision=12)
        self.patch(REMOTE, 13, 12, [
            {'op': 'replace', 'path': ['threadRuntimeStatus', 'activeFlags'], 'value': ['waitingOnUserInput']},
        ])
        self.assertEqual(self.statuses()[remote_key], 'input')
