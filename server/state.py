"""Metadata-only projection of the desktop's v11 thread stream.

Raw messages/transcripts are never persisted. Only the explicitly selected fields
below survive a frame. In particular a tool item's status is not a turn status.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any

if __package__:
    from .localization import text
else:
    from localization import text


TURN_FIELDS = {"turnId", "id", "status", "turnStartedAtMs", "durationMs"}
THREAD_FIELDS = {"id", "title", "workspaceKind", "projectId", "parentThreadId",
                 "ephemeral", "threadRuntimeStatus", "hasUnreadTurn", "updatedAt", "cwd", "hostId", "threadSource"}
TERMINAL = {"completed", "failed", "interrupted"}


def thread_key(host_id: str, thread_id: str) -> str:
    # Preserve every existing local ID and its saved numbering contract.
    return thread_id if host_id == "local" else host_id + "::" + thread_id


def split_thread_key(key: str) -> tuple[str, str]:
    return tuple(key.rsplit("::", 1)) if "::" in key else ("local", key)


def turn_metadata(value: Any) -> dict:
    return {k: v for k, v in value.items() if k in TURN_FIELDS} if isinstance(value, dict) else {}


def request_metadata(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    return {k: value[k] for k in ("id", "method", "completedAtMs") if k in value}


def project_snapshot(raw: dict) -> dict:
    out = {k: copy.deepcopy(raw[k]) for k in THREAD_FIELDS if k in raw}
    out["requests"] = [request_metadata(r) for r in raw.get("requests", [])]
    out["externalRequests"] = [request_metadata(r) for r in raw.get("externalRequests", [])]
    out["turns"] = [turn_metadata(t) for t in raw.get("turns", [])]
    history = raw.get("turnHistory", {}).get("history", {}) or {}
    entities = history.get("entitiesByKey", {}) or {}
    out["turnHistory"] = {"history": {"entitiesByKey": {
        k: turn_metadata(v) for k, v in entities.items()
    }}}
    return out


def project_patch(patch: dict) -> dict | None:
    """Keep paths needed by the projection, stripping bodies at parent replacements."""
    path = patch.get("path", [])
    if not path:
        return {**patch, "value": project_snapshot(patch.get("value", {}))}
    first, value = path[0], patch.get("value")
    if first in THREAD_FIELDS:
        return copy.deepcopy(patch)
    if first in ("requests", "externalRequests"):
        if len(path) == 1:
            value = [request_metadata(r) for r in value] if isinstance(value, list) else []
        elif len(path) == 2:
            value = request_metadata(value)
        elif path[-1] not in ("id", "method", "completedAtMs"):
            return None
        return {**patch, "value": value}
    if first == "turns":
        if len(path) == 1:
            value = [turn_metadata(t) for t in value] if isinstance(value, list) else []
        elif len(path) == 2:
            value = turn_metadata(value)
        elif len(path) != 3 or path[2] not in TURN_FIELDS:
            return None
        return {**patch, "value": value}
    if first == "turnHistory":
        if "items" in path or "content" in path:
            return None
        if len(path) == 1:
            value = project_snapshot({"turnHistory": value})["turnHistory"]
        elif path[:3] == ["turnHistory", "history", "entitiesByKey"]:
            if len(path) == 3:
                value = {k: turn_metadata(v) for k, v in (value or {}).items()}
            elif len(path) == 4:
                value = turn_metadata(value)
            elif len(path) != 5 or path[-1] not in TURN_FIELDS:
                return None
        elif path == ["turnHistory", "history"]:
            value = project_snapshot({"turnHistory": {"history": value}})["turnHistory"]["history"]
        else:
            return None
        return {**patch, "value": value}
    return None


def apply_patch(root: Any, patch: dict) -> Any:
    """Apply Immer-style array-path add/replace/remove to the projected tree."""
    path, op = patch.get("path", []), patch["op"]
    if not path:
        return copy.deepcopy(patch.get("value", {}))
    node = root
    for segment in path[:-1]:
        node = node[segment]
    key = path[-1]
    if op == "remove":
        if isinstance(node, list):
            node.pop(int(key))
        else:
            node.pop(key, None)
    elif op in ("add", "replace"):
        value = copy.deepcopy(patch.get("value"))
        if isinstance(node, list) and op == "add":
            node.insert(int(key), value)
        else:
            node[key] = value
    else:
        raise ValueError(f"Unsupported patch operation: {op}")
    return root


@dataclass
class ThreadState:
    id: str
    revision: int | None = None
    metadata: dict = field(default_factory=dict)
    valid: bool = False
    owner: str | None = None
    host_id: str = "local"

    @property
    def key(self) -> str:
        return thread_key(self.host_id, self.id)

    def consume(self, change: dict, owner: str | None) -> bool:
        if change.get("type") == "snapshot":
            if self.valid and self.owner == owner and change["revision"] < self.revision:
                return True
            self.metadata = project_snapshot(change.get("conversationState", {}))
            self.revision, self.owner, self.valid = change["revision"], owner, True
            return True
        if (change.get("type") != "patches" or not self.valid
                or self.owner != owner or change.get("baseRevision") != self.revision):
            self.valid = False
            return False
        try:
            for raw in change.get("patches", []):
                selected = project_patch(raw)
                if selected is not None:
                    self.metadata = apply_patch(self.metadata, selected)
        except (KeyError, IndexError, TypeError, ValueError):
            self.valid = False
            return False
        # Advance for EVERY frame, including frames containing only dropped text.
        self.revision = change["revision"]
        return True

    @property
    def latest_turn(self) -> dict:
        turns = [t for t in self.metadata.get("turns", []) if isinstance(t, dict)]
        turns += list(self.metadata.get("turnHistory", {}).get("history", {})
                      .get("entitiesByKey", {}).values())
        turns = [t for t in turns if t.get("turnId") or t.get("id")]
        # Canonical dictionaries are not chronology. UUIDv7 turn IDs break equal
        # or absent timestamp ties without ever inspecting message content.
        return max(turns, key=lambda t: (t.get("turnStartedAtMs") or 0,
                   t.get("turnId", t.get("id", "")))) if turns else {}

    def phase(self) -> str:
        if not self.valid:
            return "unknown"
        runtime = self.metadata.get("threadRuntimeStatus") or {}
        kind, flags = runtime.get("type"), runtime.get("activeFlags", [])
        requests = self.metadata.get("requests", []) + self.metadata.get("externalRequests", [])
        methods = [r.get("method", "") for r in requests if r.get("completedAtMs") is None]
        if kind == "active":
            if "waitingOnApproval" in flags or any("requestApproval" in m for m in methods):
                return "approval"
            if "waitingOnUserInput" in flags or any("requestUserInput" in m or "elicitation/request" in m for m in methods):
                return "input"
            return "running"
        if kind == "systemError":
            return "failed"
        terminal = self.latest_turn.get("status")
        if terminal in TERMINAL:
            return {"completed": "completed", "failed": "failed", "interrupted": "stopped"}[terminal]
        if terminal == "inProgress" and kind in ("idle", "notLoaded"):
            return "unknown"
        return "unknown" if kind == "notLoaded" else "idle"


PHASE_NAMES = {"running": "进行中", "approval": "等待授权", "input": "等待你回答",
               "completed": "本轮已完成", "failed": "运行失败", "stopped": "已停止",
               "unknown": "状态未知", "idle": "空闲"}


class WatchRegistry:
    """Persist historical identity/slots; project visible ordinals independently."""

    def __init__(self, saved: dict | None = None):
        self.entries: dict[str, dict] = copy.deepcopy((saved or {}).get("entries", {}))
        self.next_number: dict[str, int] = dict((saved or {}).get("nextNumber", {}))
        self.acknowledged: dict[str, str] = dict((saved or {}).get("acknowledged", {}))
        self.hidden: dict[str, dict] = copy.deepcopy((saved or {}).get("hiddenThreads", {}))

    def hide(self, key: str, reason: str, context: dict) -> None:
        self.hidden[key] = {"reason": reason, "projectMetadata": context if reason == "archived" else {}}
        self.entries.pop(key, None)

    def mark_seen(self, thread: ThreadState) -> None:
        if thread.phase() in ("completed", "failed", "stopped"):
            turn = thread.latest_turn
            self.acknowledged[thread.key] = turn.get("turnId", turn.get("id", ""))
            self.entries.pop(thread.key, None)

    def mark_unread(self, thread: ThreadState) -> None:
        # Only an explicit desktop unread edge rearms this known turn. Ordinary
        # (possibly stale) unread snapshots must not undo a local acknowledgement.
        turn = thread.latest_turn
        turn_id = turn.get("turnId") or turn.get("id")
        if turn_id and self.acknowledged.get(thread.key) == turn_id:
            self.acknowledged.pop(thread.key)

    def update(self, states: dict[str, ThreadState], projects: dict, connected: bool, *, language="zh-CN") -> list[dict]:
        now = time.time()
        for tid, state in states.items():
            if tid in self.hidden:
                self.entries.pop(tid, None)
                continue
            m, phase = state.metadata, state.phase()
            if m.get("ephemeral") or m.get("parentThreadId"):
                continue
            turn = state.latest_turn
            turn_id = turn.get("turnId", turn.get("id", ""))
            is_unseen = m.get("hasUnreadTurn") is True and self.acknowledged.get(tid) != turn_id
            should_watch = phase in ("running", "approval", "input") or (phase in ("completed", "failed", "stopped") and is_unseen)
            if phase == "unknown" and tid in self.entries:
                should_watch = True
            if not should_watch:
                self.entries.pop(tid, None)
                continue
            project = projects.get(tid)
            if project is None:
                project = ({"id": "unresolved:" + tid, "name": "项目待同步", "kind": "pending", "markerType": "icon", "marker": "folder"}
                           if m.get("workspaceKind") == "project" else
                           {"id": "ungrouped", "name": "未分组", "kind": "chat-bucket", "markerType": "icon", "marker": "message-circle"})
                if state.host_id != "local":
                    project = {**project, "id": thread_key(state.host_id, project["id"]),
                               "hostId": state.host_id, "hostLabel": None}
            old = self.entries.get(tid)
            if old is None or old["project"]["id"] != project["id"]:
                pid = project["id"]
                number = self.next_number.get(pid, 1)
                self.next_number[pid] = number + 1
                old = {"id": tid, "threadId": state.id, "hostId": state.host_id,
                       "index": number, "phase": phase, "since": now,
                       "firstSeen": now, "project": project}
                self.entries[tid] = old
            if old["phase"] != phase:
                old["phase"], old["since"] = phase, now
            old.update({"threadId": state.id, "hostId": state.host_id,
                        "project": project, "title": m.get("title") or "未命名聊天",
                        "canMarkSeen": phase in ("completed", "failed", "stopped")})
        active_projects = {e["project"]["id"] for e in self.entries.values()}
        self.next_number = {k: v for k, v in self.next_number.items() if k in active_projects}
        groups: dict[str, dict] = {}
        for entry in sorted(self.entries.values(), key=lambda e: e["firstSeen"]):
            project = entry["project"]
            group = groups.setdefault(project["id"], {**project, "threads": []})
            if project.get("kind") in ("chat-bucket", "pending"):
                group["name"] = text("chatBucket" if project["kind"] == "chat-bucket" else "pendingProject", language)
            source = states.get(entry["id"])
            phase = entry["phase"] if connected and source is not None and source.valid else "unknown"
            group["threads"].append({k: entry[k] for k in ("id", "title", "since")} | {
                "index": len(group["threads"]) + 1,
                "title": text("untitledChat", language) if source and not source.metadata.get("title") else entry["title"],
                "threadId": entry.get("threadId", entry["id"]), "hostId": entry.get("hostId", "local"),
                "status": phase, "detail": text(phase, language),
                "canMarkSeen": phase in ("completed", "failed", "stopped")})
        return list(groups.values())

    def saved(self) -> dict:
        saved = {"entries": self.entries, "nextNumber": self.next_number,
                 "acknowledged": self.acknowledged}
        if self.hidden:
            saved["hiddenThreads"] = self.hidden
        return saved
