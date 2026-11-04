import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server"))
from state import ThreadState, WatchRegistry


def snapshot(kind="active", unread=False, status="inProgress", flags=None):
    return {"type": "snapshot", "revision": 1, "conversationState": {
        "id": "chat", "title": "测试聊天", "workspaceKind": "project",
        "threadRuntimeStatus": {"type": kind, "activeFlags": flags or []},
        "hasUnreadTurn": unread, "requests": [],
        "turns": [], "turnHistory": {"history": {"entitiesByKey": {"tail:0": {
            "turnId": "turn-2", "status": status, "turnStartedAtMs": 200,
            "items": [{"text": "NEVER PERSIST THIS", "status": "completed"}]
        }, "tail:1": {"turnId": "turn-1", "status": "completed", "turnStartedAtMs": 100}}}}
    }}


def patch(revision, patches):
    return {"type": "patches", "baseRevision": revision - 1, "revision": revision, "patches": patches}


class StateTests(unittest.TestCase):
    def test_snapshot_strips_transcript_and_orders_turns(self):
        state = ThreadState("chat")
        self.assertTrue(state.consume(snapshot(), "owner"))
        self.assertNotIn("NEVER PERSIST", str(state.metadata))
        self.assertEqual(state.latest_turn["turnId"], "turn-2")
        self.assertEqual(state.phase(), "running")

    def test_text_only_patch_advances_revision(self):
        state = ThreadState("chat")
        state.consume(snapshot(), "owner")
        state.consume(patch(2, [{"op": "add", "path": ["turnHistory", "history", "entitiesByKey", "tail:0", "items", 1], "value": {"text": "body"}}]), "owner")
        self.assertEqual(state.revision, 2)
        self.assertTrue(state.consume(patch(3, [{"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "active", "activeFlags": ["waitingOnApproval"]}}]), "owner"))
        self.assertEqual(state.phase(), "approval")

    def test_tool_completed_does_not_complete_chat(self):
        state = ThreadState("chat")
        state.consume(snapshot(), "owner")
        state.consume(patch(2, [{"op": "replace", "path": ["turnHistory", "history", "entitiesByKey", "tail:0", "items", 0, "status"], "value": "completed"}]), "owner")
        self.assertEqual(state.phase(), "running")
        self.assertEqual(state.latest_turn["status"], "inProgress")

    def test_revision_gap_or_new_owner_invalidates(self):
        state = ThreadState("chat")
        state.consume(snapshot(), "owner")
        self.assertFalse(state.consume(patch(3, []), "owner"))
        self.assertEqual(state.phase(), "unknown")
        state.consume(snapshot(), "new")
        self.assertFalse(state.consume(patch(2, []), "old"))

    def test_complete_turn_and_wait_for_input(self):
        state = ThreadState("chat")
        state.consume(snapshot(flags=["waitingOnUserInput"]), "owner")
        self.assertEqual(state.phase(), "input")
        state.consume(patch(2, [
            {"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "idle"}},
            {"op": "replace", "path": ["turnHistory", "history", "entitiesByKey", "tail:0", "status"], "value": "completed"},
            {"op": "replace", "path": ["hasUnreadTurn"], "value": True}]), "owner")
        self.assertEqual(state.phase(), "completed")

    def test_watch_completion_seen_and_current_display_ordinal(self):
        a, b = ThreadState("a"), ThreadState("b")
        a.consume(snapshot(), "owner")
        b.consume(snapshot(), "owner")
        project = {"id": "p", "name": "项目", "markerType": "emoji", "marker": "📚"}
        registry = WatchRegistry()
        states, projects = {"a": a, "b": b}, {"a": project, "b": project}
        group = registry.update(states, projects, True)[0]
        self.assertEqual([t["index"] for t in group["threads"]], [1, 2])
        a.consume(snapshot("idle", True, "completed"), "owner")
        self.assertEqual(registry.update(states, projects, True)[0]["threads"][0]["status"], "completed")
        a.metadata["hasUnreadTurn"] = False
        group = registry.update(states, projects, True)[0]
        self.assertEqual([t["index"] for t in group["threads"]], [1])
        self.assertEqual(registry.entries['b']['index'], 2)  # Saved historical slot is retained.
        self.assertEqual(registry.update(states, projects, False)[0]["threads"][0]["status"], "unknown")

    def test_idle_history_excluded_and_manual_seen_is_local(self):
        state = ThreadState("chat")
        state.consume(snapshot("idle", False, "completed"), "owner")
        registry = WatchRegistry()
        self.assertEqual(registry.update({"chat": state}, {}, True), [])
        state.metadata["hasUnreadTurn"] = True
        registry.update({"chat": state}, {}, True)
        registry.mark_seen(state)
        self.assertTrue(state.metadata["hasUnreadTurn"])
        self.assertEqual(registry.update({"chat": state}, {}, True), [])

    def test_between_runtime_and_turn_end_keeps_slot(self):
        state = ThreadState("chat")
        state.consume(snapshot(), "owner")
        registry = WatchRegistry()
        registry.update({"chat": state}, {}, True)
        state.consume(patch(2, [{"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "idle"}}]), "owner")
        group = registry.update({"chat": state}, {}, True)[0]
        self.assertEqual(group["threads"][0]["index"], 1)
        self.assertEqual(group["threads"][0]["status"], "unknown")

    def test_old_snapshot_does_not_erase_new_turn(self):
        state = ThreadState("chat")
        state.consume(snapshot(), "owner")
        state.consume(patch(2, [{"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "active", "activeFlags": ["waitingOnApproval"]}}]), "owner")
        state.consume(snapshot(), "owner")
        self.assertEqual(state.phase(), "approval")
        self.assertEqual(state.revision, 2)


if __name__ == "__main__":
    unittest.main()
