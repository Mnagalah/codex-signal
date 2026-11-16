"""Cold and live unread badges from a fictional Codex profile."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from test_read_sync import ReadSyncFixture, TID, snapshot, thread_key
from availability import LocalThreadAvailability, RemoteThreadCatalog
from desktop import DesktopMetadata
from state import WatchRegistry

OTHER = "22222222-2222-4222-8222-222222222222"
THIRD = "33333333-3333-4333-8333-333333333333"
REMOTE = "remote-control:sample"
OFFLINE = "remote-control:offline"
IDENTITY = "7" * 64


class DesktopUnreadTests(ReadSyncFixture):
    def setUp(self):
        super().setUp()
        self.path = Path(self.tmp.name) / "desktop.json"
        self.db = Path(self.tmp.name) / "state.sqlite"
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, cwd TEXT, archived INTEGER, "
                       "thread_source TEXT, attached_thread_parent_id TEXT)")
            db.executemany("INSERT INTO threads VALUES (?, ?, '/fictional', 0, 'user', NULL)",
                           [(TID, "Tracked chat"), (OTHER, "Independent chat"), (THIRD, "Another chat")])
        self.catalog_path = Path(self.tmp.name) / "catalog.sqlite"
        with closing(sqlite3.connect(self.catalog_path)) as db, db:
            db.execute("CREATE TABLE local_thread_catalog (host_id TEXT, thread_id TEXT, cwd TEXT, "
                       "missing_candidate INTEGER, PRIMARY KEY(host_id, thread_id))")
        self.p.remote_catalog = RemoteThreadCatalog(self.catalog_path)
        self.p.metadata = DesktopMetadata(self.path)
        self.p.availability = LocalThreadAvailability(self.db)
        self.p.states.clear()
        self.p.registry.entries.clear()

    def write(self, *, local=(), remote=(), offline=(), identity=IDENTITY, generation="a", extra_accounts=None, **metadata):
        hosts = {"local:" + generation * 64: list(local), REMOTE + ":" + "c" * 64: list(remote),
                 OFFLINE + ":" + "d" * 64: list(offline)}
        replacement = self.path.with_suffix(".tmp")
        replacement.write_text(json.dumps({
            "electron-thread-read-state-v1": {
                "version": 1, "unreadByIdentity": {identity: hosts, **(extra_accounts or {})},
            },
            "local-projects": {"project": {"name": "Fictional project"}},
            "thread-project-assignments": {tid: {"projectKind": "local", "projectId": "project"}
                                           for tid in (TID, OTHER, THIRD)},
            **metadata,
        }))
        replacement.replace(self.path)
        self.p.metadata.poll()
        self.p.sync_desktop_unread()
        self.p.reconcile_availability()
        self.p.publish()

    def phases(self):
        return {chat["id"]: chat["status"] for chat in self.chats()}

    def stream(self, host="local", phase="completed", unread=True, revision=1):
        self.p.consume_ipc(self.p.ipc, {
            "type": "broadcast", "method": "thread-stream-state-changed", "version": 13,
            "sourceClientId": "owner:" + host, "params": {
                "hostId": host, "conversationId": TID,
                "change": snapshot(phase=phase, unread=unread, revision=revision),
            },
        })
        self.p.publish()

    def test_two_never_followed_local_chats_appear_and_clear_without_snapshot(self):
        self.write()
        self.assertEqual(self.phases(), {})
        self.write(local=(OTHER, THIRD))
        self.assertEqual(self.phases(), {OTHER: "unread", THIRD: "unread"})
        self.assertEqual([chat["index"] for chat in self.chats()], [1, 2])
        self.assertEqual({chat["title"] for chat in self.chats()}, {"Independent chat", "Another chat"})
        self.assertFalse(any(chat["canMarkSeen"] for chat in self.chats()))
        self.assertTrue(all(not self.p.recovery.pending[key].required for key in (OTHER, THIRD)))
        self.assertEqual(self.p.notice_emitted, 0)
        kept = self.p.registry.entries[THIRD]["firstSeen"]
        self.write(local=(THIRD,))
        self.assertEqual(self.phases(), {THIRD: "unread"})
        self.assertEqual(self.p.registry.entries[THIRD]["firstSeen"], kept)
        self.write()
        self.assertEqual(self.phases(), {})
        self.assertEqual(self.p.recovery.pending, {})

    def test_bootstrap_does_not_infer_completion_or_change_active_tasks(self):
        self.write(local=(OTHER,))
        self.stream(phase="inProgress")
        self.assertEqual(self.phases(), {TID: "running", OTHER: "unread"})
        self.write()
        self.assertEqual(self.phases(), {TID: "running"})

    def test_read_store_wins_over_stale_stream_but_not_task_phase(self):
        self.write(local=(TID,))
        self.stream()
        self.assertEqual(self.phases(), {TID: "completed"})
        self.write()
        self.stream(unread=True, revision=2)
        self.assertEqual(self.phases(), {})
        self.stream(phase="inProgress", revision=3)
        self.assertEqual(self.phases(), {TID: "running"})
        self.write(local=(TID,))
        self.stream(phase="completed", unread=False, revision=4)
        self.assertEqual(self.phases(), {TID: "completed"})

    def test_same_id_other_host_and_offline_bucket_do_not_cross(self):
        self.stream(host=REMOTE, phase="inProgress")
        self.write(local=(TID,), remote=(OTHER,), offline=(THIRD,))
        self.assertEqual(self.phases(), {TID: "unread", thread_key(REMOTE, TID): "running",
                                         thread_key(REMOTE, OTHER): "unread"})
        self.write(remote=(OTHER,), offline=(THIRD,))
        self.assertEqual(self.phases(), {thread_key(REMOTE, TID): "running",
                                         thread_key(REMOTE, OTHER): "unread"})
        self.write()
        self.assertEqual(self.phases(), {thread_key(REMOTE, TID): "running"})

    def test_never_followed_remote_matches_desktop_project_without_a_snapshot(self):
        projects = [
            {"id": "a", "hostId": REMOTE, "label": "Remote root", "remotePath": "/sample/root"},
            {"id": "b", "hostId": REMOTE, "label": "Remote nested", "remotePath": "/sample/root/nested"},
            {"id": "c", "hostId": OFFLINE, "label": "Other host", "remotePath": "/sample/root/nested/x"},
        ]
        self.stream(host=REMOTE, phase="inProgress")
        self.write(remote=(OTHER, THIRD), **{"remote-projects": projects})
        key = thread_key(REMOTE, OTHER)
        original = self.p.registry.entries[key]["firstSeen"]
        self.assertEqual(self.p.registry.entries[key]["project"]["kind"], "chat-bucket")
        with closing(sqlite3.connect(self.catalog_path)) as db, db:
            db.executemany("INSERT INTO local_thread_catalog VALUES (?, ?, ?, ?)", [
                (REMOTE, OTHER, "/sample/root/nested/x", 0),
                (REMOTE, THIRD, "/sample/root", 1),
                (OFFLINE, THIRD, "/sample/root/nested/x", 0),
                (REMOTE, "unlisted-id", "/sample/root", 0),
            ])
        # The catalog catches up without a read-state file rewrite or snapshot.
        self.p.sync_desktop_unread()
        self.p.publish()
        entry = self.p.registry.entries[key]
        self.assertEqual(entry["project"]["name"], "Remote nested")
        self.assertEqual(entry["project"]["id"], thread_key(REMOTE, "b"))
        self.assertEqual(entry["firstSeen"], original)
        self.assertEqual(self.phases()[key], "unread")
        self.assertEqual(self.p.registry.entries[thread_key(REMOTE, THIRD)]["project"]["kind"], "chat-bucket")
        pid = thread_key(REMOTE, "b")
        self.p.paused_projects[pid] = entry["project"]
        # Reproduce a retained old Chat slot when the correct project is paused.
        entry["project"] = self.p.registry.entries[thread_key(REMOTE, THIRD)]["project"]
        self.p.publish()
        self.assertNotIn(key, self.phases())
        self.assertEqual(self.p.registry.entries[key]["firstSeen"], original)
        self.p.paused_projects.clear()
        self.p.publish()
        self.assertEqual(self.p.registry.entries[key]["project"]["id"], pid)
        self.assertEqual(self.phases()[key], "unread")
        self.assertNotIn(thread_key(REMOTE, "unlisted-id"), self.p.states)
        self.assertEqual(self.p.notice_emitted, 0)
        self.write(remote=(THIRD,), **{"remote-projects": projects})
        self.assertNotIn(key, self.phases())

    def test_catalog_does_not_override_explicit_no_project_or_fresh_project(self):
        data = {"remote-projects": [
            {"id": "a", "hostId": REMOTE, "label": "Old", "remotePath": "/old"},
            {"id": "b", "hostId": REMOTE, "label": "Current", "remotePath": "/new"},
        ]}
        self.stream(host=REMOTE, phase="inProgress")
        key = thread_key(REMOTE, OTHER)
        with closing(sqlite3.connect(self.catalog_path)) as db, db:
            db.execute("INSERT INTO local_thread_catalog VALUES (?, ?, '/old', 0)", (REMOTE, OTHER))
        self.write(remote=(OTHER,), **{**data, "projectless-thread-ids": [OTHER]})
        self.assertEqual(self.p.registry.entries[key]["project"]["kind"], "chat-bucket")
        self.write(remote=(OTHER,), **data)
        self.assertEqual(self.p.registry.entries[key]["project"]["name"], "Old")
        state = self.p.states[key]
        state.valid = True
        state.metadata.update(cwd="/new/path", workspaceKind="project")
        self.p.sync_desktop_unread()
        self.p.publish()
        self.assertEqual(self.p.registry.entries[key]["project"]["name"], "Current")
        state.metadata["workspaceKind"] = "projectless"
        self.p.publish()
        self.assertEqual(self.p.registry.entries[key]["project"]["kind"], "chat-bucket")
        self.assertEqual(self.phases()[key], "unread")

    def test_remote_reader_only_badge_waits_for_reconnect_without_health_timeout(self):
        self.stream(host=REMOTE, phase="inProgress")
        self.write(remote=(OTHER,))
        key = thread_key(REMOTE, OTHER)
        saved = self.p.registry.saved()
        slot = saved["entries"][key].copy()

        # A new plugin payload has the saved slots but not the live snapshots.
        self.p.states.clear()
        self.p.unread_candidates.clear()
        self.p.registry = WatchRegistry(saved)
        self.p.registry.entries.pop(thread_key(REMOTE, TID))
        self.p.recovery.pending.clear()
        self.p.connected = False
        self.p.begin_snapshot_handoff()
        self.assertEqual(self.p.resume_snapshots, {})
        self.p.publish()
        self.assertEqual(self.phases(), {key: "unknown"})
        self.p.connected = True
        self.p.expect_snapshot(key, baseline=True)
        self.assertFalse(self.p.recovery.pending[key].required)
        self.stream(host=REMOTE, phase="inProgress")
        self.write(remote=(OTHER,))
        self.assertEqual(self.phases()[key], "unread")
        self.assertEqual(self.p.registry.entries[key]["firstSeen"], slot["firstSeen"])
        self.assertEqual(self.p.registry.entries[key]["index"], slot["index"])

        self.p.consume_client_lifecycle(self.p.ipc, {
            "method": "client-status-changed", "params": {"clientId": "owner:" + REMOTE, "status": "disconnected"},
        })
        self.write(remote=(OTHER,))
        self.assertNotIn(key, self.phases())
        self.assertNotIn(key, self.p.recovery.pending)

    def test_file_unread_edge_rearms_same_terminal_turn_after_reload(self):
        self.write(local=(TID,))
        self.stream()
        self.p.registry.mark_seen(self.p.states[TID])
        self.p.publish()
        self.assertEqual(self.phases(), {})
        self.write()
        self.write(local=(TID,))
        self.assertEqual(self.phases(), {TID: "completed"})
        self.assertNotIn(TID, self.p.registry.acknowledged)
        self.p.registry = WatchRegistry(self.p.registry.saved())
        self.p.unread.added.clear()
        self.p.publish()
        self.assertEqual(self.phases(), {TID: "completed"})

    def test_archived_deleted_and_child_rows_not_admitted(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE threads SET archived=1 WHERE id=?", (TID,))
            db.execute("DELETE FROM threads WHERE id=?", (OTHER,))
            db.execute("UPDATE threads SET attached_thread_parent_id=? WHERE id=?", (OTHER, THIRD))
        self.write(local=(TID, OTHER, THIRD))
        self.assertEqual(self.phases(), {})

    def test_ambiguous_accounts_and_aliases_not_combined(self):
        self.write(local=(OTHER,), extra_accounts={"8" * 64: {"local:" + "a" * 64: [THIRD]}})
        self.assertEqual(self.phases(), {})
        data = json.loads(self.path.read_text())
        store = data["electron-thread-read-state-v1"]["unreadByIdentity"]
        store.pop("8" * 64)
        store[IDENTITY]["local:" + "b" * 64] = [THIRD]
        self.path.write_text(json.dumps(data))
        self.p.metadata.poll()
        self.p.sync_desktop_unread()
        self.p.publish()
        self.assertEqual(self.phases(), {})

    def test_explicit_read_precedes_file_flush_and_new_unread_reappears(self):
        self.write(local=(TID,))
        self.stream()
        self.read()
        self.p.publish()
        self.assertEqual(self.phases(), {})
        self.write(local=(TID, OTHER))  # Unrelated update must not resurrect TID.
        self.assertEqual(self.phases(), {OTHER: "unread"})
        self.write(local=(OTHER,))
        self.write(local=(TID, OTHER))
        self.assertEqual(self.phases(), {TID: "completed", OTHER: "unread"})

    def test_paused_project_suppresses_unread_without_dropping_old_slot(self):
        self.write(local=(OTHER,))
        saved = self.p.registry.entries[OTHER]["firstSeen"]
        self.p.paused_projects["project"] = {"id": "project"}
        self.write()
        self.assertEqual(self.phases(), {})
        self.assertEqual(self.p.registry.entries[OTHER]["firstSeen"], saved)
        self.p.paused_projects.clear()
        self.p.publish()
        self.assertEqual(self.phases(), {})
