#!/usr/bin/env python3
"""Plugin-owned stdio MCP process. Its child is a renderer, never an app install."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import queue
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode

if __package__:
    from .desktop import DesktopIPC, DesktopMetadata
    from .state import ThreadState, WatchRegistry, thread_key, split_thread_key
    from .control import enqueue, latest_release, pending, write_json
    from .localization import DesktopLanguage, connection_text, text
    from .notifications import NoticeTracker
    from .resume_probe import ProjectResumeProbe
    from .lifecycle import load_plugin_class, prune_payload_modules
    from .availability import LocalThreadAvailability
    from .recovery import Recovery
    from . import runtime_paths
else:
    from desktop import DesktopIPC, DesktopMetadata
    from state import ThreadState, WatchRegistry, thread_key, split_thread_key
    from control import enqueue, latest_release, pending, write_json
    from localization import DesktopLanguage, connection_text, text
    from notifications import NoticeTracker
    from resume_probe import ProjectResumeProbe
    from lifecycle import load_plugin_class, prune_payload_modules
    from availability import LocalThreadAvailability
    from recovery import Recovery
    import runtime_paths

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = "0.2.7"
RESUME_SNAPSHOT_WAIT = 5.0
UUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


def chat_url(reference: str) -> str | None:
    host_id, tid = split_thread_key(reference)
    if not UUID.fullmatch(tid):
        return None
    url = "codex://threads/" + tid
    # Matches this desktop build's own existing-thread link producer.
    return url if host_id == "local" else url + "?" + urlencode({"hostId": host_id})


def atomic_json(path: pathlib.Path, value: dict) -> None:
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp, path)


def load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Plugin:
    def __init__(self, args, *, events=None, lock=None):
        if __package__:
            prune_payload_modules(__package__)
        self.args = args
        self.events: queue.Queue = events if events is not None else queue.Queue()
        self.data = runtime_paths.data_directory()
        self.settings_path = runtime_paths.settings_path(self.data)
        self.settings_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.data.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = lock if lock is not None else open(self.data / "monitor.lock", "a+")
        os.chmod(self.data / "monitor.lock", 0o600)
        self.primary = False
        self.ipc: DesktopIPC | None = None
        self.renderer: subprocess.Popen | None = None
        self.states: dict[str, ThreadState] = {}
        self.registry = WatchRegistry()
        self.metadata = DesktopMetadata(runtime_paths.desktop_state())
        self.availability = LocalThreadAvailability(runtime_paths.desktop_state_db())
        self.language = DesktopLanguage(runtime_paths.desktop_config())
        self.connected = False
        self.detail = "正在连接 Codex"
        self.running = True
        self.retry_at = 0.0
        self.handshake_deadline = 0.0
        self.refresh_at = 0.0
        self.last_ui = None
        self.last_save = None
        self.last_status = {"connected": False, "projects": [], "detail": self.detail}
        self.started = time.monotonic()
        self.refresh_pending = False
        self.pending_discovery: set[str] = set()
        self.pending_unread: set[str] = set()
        self.protocol_errors: set[tuple[str, str]] = set()
        self.event_counts: dict[str, int] = {}
        self.ui_error: str | None = None
        self.ui_ready = False
        self.ui_layout = None
        self.enabled = load_json(self.settings_path).get("enabled", True) is not False
        self.reload_requested = False
        self.update_error = None
        self.notices = NoticeTracker()
        self.pending_notice = None
        self.notice_emitted = 0
        self.notice_receipts = {"shown": 0, "closed": 0, "opened": 0, "diagnosticShown": 0}
        self.notice_target = None
        self.paused_projects = load_json(self.settings_path).get("pausedProjects", {})
        settings = load_json(self.settings_path)
        self.notification_states = set(settings.get("notificationStates", NoticeTracker.PHASES)) & NoticeTracker.PHASES
        self.compact_menu_bar = settings.get("compactMenuBar") is True
        self.status_emoji = settings.get("statusEmoji", "🔦")
        self.notice_phase = None
        self.project_catalog = {}
        self.project_by_thread = {}
        self.resume_snapshots: dict[str, float] = {}
        self.resume_connecting = False
        self.resume_probe = None
        self.recovery = Recovery()
        self.last_recovery_save = None

    def start_reader(self, kind: str, stream) -> None:
        events = self.events
        source = self.renderer if kind == "ui" else None
        def run():
            try:
                for line in stream:
                    try:
                        value = json.loads(line)
                        events.put((kind, (source, value) if kind == "ui" else value))
                    except (ValueError, UnicodeError):
                        events.put((kind + "_invalid", source))
            finally:
                events.put((kind + "_eof", source))
        threading.Thread(target=run, daemon=True, name=kind).start()

    def elect(self) -> None:
        if self.primary:
            return
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        self.primary = True
        # A standby MCP client may outlive its installed cache version. On
        # acquiring ownership, adopt the complete same-source update before
        # starting a renderer or publishing stale state. Reuse the transport
        # queue and lock through the existing payload reload path. A failed
        # update must retain its reported fallback, not enter a retry loop.
        if self.update_error is None and latest_release(ROOT) != ROOT:
            self.reload_requested, self.running = True, False
            return
        self.enabled = load_json(self.settings_path).get("enabled", True) is not False
        if not self.enabled:
            self.detail = "监控已关闭"
        self.paused_projects = load_json(self.settings_path).get("pausedProjects", {})
        settings = load_json(self.settings_path)
        self.notification_states = set(settings.get("notificationStates", NoticeTracker.PHASES)) & NoticeTracker.PHASES
        self.compact_menu_bar = settings.get("compactMenuBar") is True
        self.status_emoji = settings.get("statusEmoji", "🔦")
        self.registry = WatchRegistry(load_json(self.data / "slots.json"))
        self.recovery.load(load_json(self.data / "recovery.json"))
        for key, record in self.recovery.recent.items():
            host, tid = split_thread_key(key)
            self.states.setdefault(key, ThreadState(tid, host_id=host)).metadata.update(record["projectMetadata"])
        for key, record in self.registry.hidden.items():
            host, tid = split_thread_key(key)
            self.states.setdefault(key, ThreadState(tid, host_id=host)).metadata.update(record["projectMetadata"])
        self.notices.seed(self.registry.entries)
        self.metadata.poll()
        self.project_by_thread.update({key: p["id"] for key, p in self.metadata.identities(self.states).items()})
        if self.enabled:
            self.begin_snapshot_handoff()
        if not self.args.no_ui:
            linux = sys.platform.startswith("linux")
            binary = ROOT / ("server/linux_renderer.py" if linux else "bin/codex-menu-bar")
            command = [sys.executable, str(binary)] if linux else [str(binary)]
            if not binary.is_file():
                self.detail = "菜单栏组件尚未编译"
            else:
                renderer_env = dict(os.environ)
                if os.environ.get("CODEX_MENU_STATUS_CAPTURE") == "1":
                    renderer_env["CODEX_MENU_UI_CAPTURE_DIR"] = str(self.data / "render-check")
                self.renderer = subprocess.Popen(command, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1, env=renderer_env)
                self.start_reader("ui", self.renderer.stdout)

    def connect(self) -> None:
        path = runtime_paths.desktop_socket()
        ipc = DesktopIPC(path)
        try:
            ipc.connect()
        except OSError as error:
            self.resume_connecting = False
            self.resume_snapshots.clear()  # A real connection failure is not loading.
            self.detail = ("本机通信权限不足" if error.errno in (1, 13) else "等待 Codex 桌面启动")
            self.retry_at = time.monotonic() + 5
            return
        self.ipc = ipc
        self.handshake_deadline = time.monotonic() + 5
        self.detail = "正在同步当前聊天"

        def receive():
            try:
                for message in ipc.messages():
                    self.events.put(("ipc", (ipc, message)))
                    message = None
            except (OSError, ValueError, TypeError):
                pass
            finally:
                self.events.put(("ipc_eof", ipc))
        threading.Thread(target=receive, daemon=True, name="desktop-ipc").start()

    def disconnect(self, detail: str) -> None:
        self.resume_connecting = False
        self.resume_snapshots.clear()
        self.connected, self.detail = False, detail
        self.handshake_deadline = 0
        self.protocol_errors.clear()
        if self.ipc:
            self.ipc.close()
        self.ipc = None
        for state in self.states.values():
            state.valid = False
        self.notices.forget(set(self.states) | set(self.registry.entries))
        self.pending_notice = self.notice_target = self.notice_phase = None
        self.recovery.pending.clear()
        self.recovery.discovery_until = 0
        self.retry_at = time.monotonic() + 3

    def recovery_keys(self):
        return {key for key in self.states.keys() | self.registry.entries.keys() | self.pending_discovery
                if key not in self.registry.hidden and not self.project_paused(key)
                and not (key in self.states and (self.states[key].metadata.get("ephemeral")
                         or self.states[key].metadata.get("parentThreadId")))}

    def expect_snapshot(self, key, *, baseline=False, required=False):
        if key not in self.registry.hidden and not self.project_paused(key):
            state = self.states.get(key)
            self.recovery.expect(key, baseline=baseline,
                required=required or (key in self.registry.entries and (state is None or not state.valid)))

    def retry_snapshots(self):
        if not self.enabled or not self.connected or not self.ipc:
            return
        self.recovery.cancel(set(self.recovery.pending) - self.recovery_keys())
        for key in self.recovery.due():
            host, tid = split_thread_key(key)
            try:
                self.ipc.follow(tid, host_id=host)
            except OSError:
                self.disconnect("状态接口暂不可用，正在重连")
                break

    def consume_client_lifecycle(self, ipc, message):
        method, params = message.get("method"), message.get("params", {})
        if method not in ("ipc-connection-reset", "client-status-changed"):
            return False
        if not isinstance(params, dict) or message.get("version", 0) != (1 if method == "ipc-connection-reset" else 0):
            self.protocol_errors.add(("*", "connection"))
            return True
        self.protocol_errors.discard(("*", "connection"))
        if method == "ipc-connection-reset":
            # A new observer session also requests the native clients' current
            # followed-ID replay, including remote hosts. Never emit a reset to
            # the shared bus or restart a native owner/model task.
            self.disconnect("与 Codex 连接中断")
            self.retry_at = 0
            return True
        client, status = params.get("clientId"), params.get("status")
        if not isinstance(client, str) or status not in ("connected", "disconnected"):
            return True
        if status == "disconnected":
            affected = {key for key, state in self.states.items() if state.owner == client}
            if affected:
                self.recovery.offline_owners.add(client)
                self.notices.forget(affected)
                for key in affected:
                    self.states[key].valid = False
                    self.expect_snapshot(key, baseline=True)
                if self.pending_notice and self.pending_notice["chat"]["id"] in affected:
                    self.pending_notice = None
                if self.notice_target and self.notice_target[1] in affected:
                    self.notice_target = None
        else:
            self.recovery.offline_owners.discard(client)
            if params.get("clientType") != "codex-menu-status-plugin" and client != ipc.client_id:
                # Do not invalidate unrelated live tasks. Reannounce follows to
                # the returning owner even if our local following set says yes.
                for key in self.recovery_keys():
                    state = self.states.get(key)
                    self.expect_snapshot(key, baseline=state is None or not state.valid)
        self.retry_snapshots()
        return True

    def consume_ipc(self, ipc: DesktopIPC, message: dict) -> None:
        if ipc is not self.ipc:
            return
        name = message.get("method", message.get("type", "unknown"))
        self.event_counts[name] = self.event_counts.get(name, 0) + 1
        if ipc.acknowledge_protocol(message):
            self.connected, self.detail = True, "正在同步当前聊天"
            self.handshake_deadline = 0
            self.recovery.offline_owners.clear()
            self.recovery.discovery_until = time.monotonic() + Recovery.DISCOVERY_WAIT
            for key in self.recovery_keys():
                if key in self.states:
                    self.states[key].valid = False
                self.expect_snapshot(key, baseline=True)
            self.notices.forget(self.recovery_keys())
            self.retry_snapshots()
            self.pending_discovery.clear()
            return
        if message.get("type") != "broadcast":
            return
        if self.consume_client_lifecycle(ipc, message):
            return
        method, params = message.get("method"), message.get("params", {})
        protocols = {"thread-stream-state-changed": ("stream", DesktopIPC.STREAM_VERSION),
                     "thread-read-state-changed": ("read", DesktopIPC.READ_VERSION),
                     "thread-archived": ("archive", DesktopIPC.ARCHIVE_VERSION),
                     "thread-unarchived": ("unarchive", DesktopIPC.UNARCHIVE_VERSION)}
        if method in protocols:
            channel, expected = protocols[method]
            if not isinstance(params, dict) or message.get("version") != expected:
                host = params.get("hostId") if isinstance(params, dict) else None
                tid = params.get("conversationId") if isinstance(params, dict) else None
                key = thread_key(host, tid) if isinstance(host, str) and isinstance(tid, str) and UUID.fullmatch(tid) else "*"
                if key in self.registry.hidden and channel in ("stream", "read"):
                    return
                if key != "*" and self.project_paused(key):
                    return
                self.protocol_errors.add((key, channel))
                if channel == "stream" and key in self.states:
                    self.states[key].valid = False
                    self.resume_snapshots.pop(key, None)
                self.detail = "Codex 状态协议已变化，请更新插件"
                self.refresh_pending = True
                return
        if not isinstance(params, dict):
            return
        tid, host = params.get("conversationId"), params.get("hostId")
        if not isinstance(host, str) or not host or not isinstance(tid, str) or not UUID.fullmatch(tid):
            return
        key = thread_key(host, tid)
        if method in ("thread-archived", "thread-unarchived"):
            channel = protocols[method][0]
            self.protocol_errors.discard((key, channel))
            self.protocol_errors.discard(("*", channel))
            if method == "thread-archived":
                if key in self.states or key in self.registry.entries or key in self.pending_discovery or (host, tid) in ipc.following:
                    self.hide_thread(key, "archived")
            elif key in self.registry.hidden:
                self.restore_thread(key)
            return
        if key in self.registry.hidden:
            return  # Late snapshots/read/follower frames cannot undo retirement.
        if self.project_paused(key):
            # Keep only explicit intent in memory while the displayed/saved
            # project stays frozen. Apply it to a fresh snapshot on resume.
            if (method == "thread-read-state-changed" and key in self.states
                    and message.get("version") == DesktopIPC.READ_VERSION):
                if params.get("hasUnreadTurn") is True:
                    self.pending_unread.add(key)
                elif params.get("hasUnreadTurn") is False:
                    self.pending_unread.discard(key)
            return
        if method == "thread-stream-following-changed" and params.get("following") is True:
            if message.get("sourceClientId") != ipc.client_id and (host, tid) not in ipc.following:
                self.states.setdefault(key, ThreadState(tid, host_id=host))
                if ipc.client_id == "initializing-client":
                    self.pending_discovery.add(key)
                else:
                    self.expect_snapshot(key, baseline=True, required=True)
                    self.retry_snapshots()
            elif key in self.recovery.pending:
                self.retry_snapshots()
        elif method == "thread-stream-state-changed":
            if message.get("sourceClientId") in self.recovery.offline_owners:
                return
            state = self.states.setdefault(key, ThreadState(tid, host_id=host))
            self.protocol_errors.discard((key, "stream"))
            self.protocol_errors.discard(("*", "stream"))
            if not self.protocol_errors and self.detail == "Codex 状态协议已变化，请更新插件":
                self.detail = "已连接当前 Codex 桌面"
            change, owner = params.get("change", {}), message.get("sourceClientId")
            owner_changed = state.owner is not None and owner != state.owner
            if not state.consume(change, owner):
                self.expect_snapshot(key, baseline=True)
                self.refresh_pending = True
            elif state.valid:
                baseline = self.recovery.received(key)
                if baseline or owner_changed:
                    self.notices.forget({key})
                self.recovery.remember(key, state.metadata)
                self.recovery.offline_owners.intersection_update(s.owner for s in self.states.values() if s.owner)
            if state.valid and key in self.pending_unread:
                if state.metadata.get("hasUnreadTurn") is True:
                    self.registry.mark_unread(state)
                self.pending_unread.discard(key)
            # The projection has now discarded every transcript body.
        elif method == "thread-read-state-changed":
            state = self.states.get(key)
            if message.get("version") == DesktopIPC.READ_VERSION and isinstance(params.get("hasUnreadTurn"), bool):
                self.protocol_errors.discard((key, "read"))
                self.protocol_errors.discard(("*", "read"))
                if state:
                    if params["hasUnreadTurn"]:
                        state.metadata["hasUnreadTurn"] = True
                        if state.valid and state.latest_turn:
                            self.registry.mark_unread(state)
                        else:
                            self.pending_unread.add(key)
                    else:
                        self.pending_unread.discard(key)
                        # Opening an already-finished chat is an explicit read
                        # edge. A repeated follower snapshot can still carry
                        # unread=True, so acknowledge only this known turn.
                        # Reads during a running/unknown turn must not silence
                        # a later completion.
                        turn = state.latest_turn
                        if (state.valid and state.phase() in ("completed", "failed", "stopped")
                                and (turn.get("turnId") or turn.get("id"))):
                            self.registry.mark_seen(state)
                            state.metadata["hasUnreadTurn"] = False
                    self.refresh_pending = True
            else:
                self.protocol_errors.add((key, "read"))
                self.refresh_pending = True

    def reload_handoff(self) -> list[dict]:
        # Keep recent identity/project context, never old transcript, turn or
        # unread values. Fresh snapshots still determine what becomes visible.
        return [{"key": key, "unreadEdge": key in self.pending_unread, "projectMetadata": {k: state.metadata[k]
                    for k in ("workspaceKind", "cwd", "projectId") if k in state.metadata}}
                for key, state in self.states.items()
                if not state.metadata.get("ephemeral") and not state.metadata.get("parentThreadId")]

    def hide_thread(self, key: str, reason: str) -> None:
        host, tid = split_thread_key(key)
        state = self.states.setdefault(key, ThreadState(tid, host_id=host))
        context = {k: state.metadata[k] for k in ("workspaceKind", "cwd", "projectId") if k in state.metadata}
        self.registry.hide(key, reason, context)
        # Retain only project context for a possible unarchive, not a deleted
        # chat's title, old turn or unread bit. Keep acknowledgements separate.
        state.metadata = dict(self.registry.hidden[key]["projectMetadata"])
        state.valid, state.revision, state.owner = False, None, None
        self.resume_snapshots.pop(key, None)
        self.pending_discovery.discard(key)
        self.pending_unread.discard(key)
        self.recovery.cancel({key})
        self.recovery.recent.pop(key, None)
        self.protocol_errors = {(k, channel) for k, channel in self.protocol_errors if k != key}
        self.notices.forget({key})
        if self.pending_notice and self.pending_notice["chat"]["id"] == key:
            self.pending_notice = None
        if self.notice_target and self.notice_target[1] == key:
            self.notice_target = None
        if self.ipc and (host, tid) in self.ipc.following:
            self.ipc.follow(tid, False, host_id=host)

    def restore_thread(self, key: str) -> None:
        self.registry.hidden.pop(key, None)
        host, tid = split_thread_key(key)
        state = self.states.setdefault(key, ThreadState(tid, host_id=host))
        state.valid = False
        self.notices.forget({key})
        if self.enabled and not self.project_paused(key):
            self.resume_snapshots[key] = time.monotonic() + RESUME_SNAPSHOT_WAIT
            if self.connected and self.ipc:
                self.expect_snapshot(key, baseline=True)
                self.retry_snapshots()
            else:
                self.pending_discovery.add(key)

    def reconcile_availability(self) -> None:
        for key, status in self.availability.poll(self.states, self.registry.entries, self.registry.hidden).items():
            if status in ("archived", "deleted"):
                if self.registry.hidden.get(key, {}).get("reason") != status:
                    self.hide_thread(key, status)
            elif key in self.registry.hidden:
                self.restore_thread(key)

    def consume_handoff(self, observed: list[dict]) -> None:
        for item in observed:
            key = item["key"]
            host, tid = split_thread_key(key)
            state = self.states.setdefault(key, ThreadState(tid, host_id=host))
            if not state.valid:
                state.metadata.update(item["projectMetadata"])
            if key not in self.registry.hidden:
                self.recovery.remember(key, state.metadata)
            self.pending_discovery.add(key)
            if item.get("unreadEdge"):
                self.pending_unread.add(key)
        # Project identity is available before deciding which followers to keep
        # paused, including remote root-path assignments.
        self.project_by_thread.update({key: p["id"] for key, p in self.metadata.identities(self.states).items()})
        if self.connected and self.ipc:
            for key in self.pending_discovery:
                if key not in self.registry.hidden and not self.project_paused(key):
                    self.expect_snapshot(key, baseline=True)
            self.retry_snapshots()
            self.pending_discovery.clear()

    def adapter_health(self) -> dict:
        if not self.enabled:
            status = "paused"
        elif any(key == "*" or not self.project_paused(key) for key, _ in self.protocol_errors):
            status = "protocol-error"
        elif self.connected:
            status = self.recovery.health() or "ready"
        elif self.ipc or self.resume_connecting:
            status = "connecting"
        else:
            status = "disconnected"
        detail = "Codex 状态协议已变化，请更新插件" if status == "protocol-error" else self.detail
        if status == "ready":
            detail = "已连接当前 Codex 桌面"
        elif status == "syncing":
            detail = "正在同步当前聊天"
        elif status == "unavailable":
            return {"status": status, "detail": text("statusUnavailable", self.language.language)}
        return {"status": status, "detail": connection_text(detail, self.language.language)}

    def refresh_tracked(self) -> None:
        if not self.connected or not self.ipc:
            return
        # Read changes are not necessarily stream patches/broadcasts, especially
        # for remote owners. Requery every chat already observed this session:
        # a finished, read chat may have left the visible registry before it is
        # marked unread again. Never discover IDs from opaque account buckets
        # or enumerate history. Repeating following is a read-only snapshot.
        for tid in tuple(self.states):
            if tid not in self.registry.hidden and not self.project_paused(tid):
                if not self.states[tid].valid:
                    self.expect_snapshot(tid, baseline=True)
                else:
                    host, actual = split_thread_key(tid)
                    try:
                        self.ipc.follow(actual, host_id=host)
                    except OSError:
                        self.disconnect("状态接口暂不可用，正在重连")
                        return
        self.retry_snapshots()

    def publish(self) -> None:
        projects = self.metadata.identities(self.states)
        self.project_by_thread = {key: value["id"] for key, value in projects.items()}
        # An explicit project resume is a snapshot hand-off, not an unknown
        # task phase. Retain the historical entry until a new snapshot arrives;
        # do not paint the returning capsule with an invented grey transition.
        now = time.monotonic()
        self.resume_snapshots = {key: deadline for key, deadline in self.resume_snapshots.items()
            if self.enabled and (self.connected or self.resume_connecting)
            and (key in self.states or key in self.registry.entries)
            and (key not in self.states or not self.states[key].valid or self.states[key].phase() == "unknown")
            and not self.project_paused(key) and now < deadline}
        if self.connected or not self.resume_snapshots:
            self.resume_connecting = False
        if self.resume_snapshots:
            self.refresh_pending = True
        syncing_projects = {self.project_by_thread.get(key) or self.registry.entries.get(key, {}).get("project", {}).get("id")
                            for key in self.resume_snapshots}
        active_states = {key: state for key, state in self.states.items()
                         if key not in self.registry.hidden and not self.project_paused(key) and key not in self.resume_snapshots}
        all_groups = self.registry.update(active_states, projects, self.connected, language=self.language.language) if self.enabled else []
        catalog = {entry["project"]["id"]: dict(entry["project"]) for entry in self.registry.entries.values()}
        catalog.update({group["id"]: {k:v for k,v in group.items() if k != "threads"} for group in all_groups})
        for pid, descriptor in self.paused_projects.items():
            catalog.setdefault(pid, descriptor)
        self.project_catalog = catalog
        group_chats = {group["id"]:group["threads"] for group in all_groups}
        controls = []
        for pid, project in catalog.items():
            chats = group_chats.get(pid, []) if self.enabled and pid not in self.paused_projects else []
            chats = [{**chat, "status":"syncing", "detail":text("syncing",self.language.language), "canMarkSeen":False}
                     if chat["id"] in self.resume_snapshots else chat for chat in chats]
            controls.append({**project,"threads":chats,"updatesEnabled":pid not in self.paused_projects,
                             "syncing":pid in syncing_projects})
        tracked_groups = [group for group in all_groups if group["id"] not in self.paused_projects]
        # Gate the whole project so menu/list ordinals don't disagree during
        # a partial multi-chat refresh. Genuine invalid/timeout states still show.
        groups = [group for group in tracked_groups if group["id"] not in syncing_projects]
        # Stop only our own followers for a paused project; never interrupt an
        # owner/model task. Retained registry entries are not updated or deleted.
        if self.enabled and self.ipc:
            for host, tid in tuple(self.ipc.following):
                if self.project_paused(thread_key(host, tid)):
                    self.ipc.follow(tid, False, host_id=host)
        if self.enabled:
            notice = self.notices.observe(active_states, tracked_groups, self.connected, self.language.language, identities=projects)
            if notice and notice["chat"]["status"] in self.notification_states:
                self.pending_notice = notice
                self.notice_emitted += 1
        else:
            self.notices.reset()
            self.pending_notice = None
            self.notice_target = None
        health = self.adapter_health()
        result = {"kind": "state", "connected": self.connected, "detail": connection_text(self.ui_error, self.language.language) if self.ui_error else health["detail"],
                  "health": health,
                  "uiLanguage": self.language.language, "languageSetting": self.language.metadata(),
                  "notificationStates": sorted(self.notification_states), "compactMenuBar": self.compact_menu_bar, "statusEmoji": self.status_emoji,
                  "projects": groups, "projectControls": controls, "enabled": self.enabled, "adapter": "desktop-ipc-v11", "pluginVersion": VERSION,
                  "menuBarReady": self.ui_ready,
                  "notifications": {"enabled": self.enabled and bool(self.notification_states), "emitted": self.notice_emitted, **self.notice_receipts}}
        if self.ui_error:
            result["uiError"] = connection_text(self.ui_error, self.language.language)
        if self.update_error:
            result["updateError"] = connection_text(self.update_error, self.language.language)
        if self.ui_layout:
            result["uiLayout"] = self.ui_layout
        self.last_status = result
        if self.resume_probe:
            self.resume_probe.observe(self,result,time.monotonic())
        if result != self.last_ui:
            atomic_json(self.data / "status.json", result)
            self.last_ui = result
            if self.renderer and self.renderer.poll() is None:
                try:
                    self.renderer.stdin.write(json.dumps(result, ensure_ascii=False) + "\n")
                    self.renderer.stdin.flush()
                except (BrokenPipeError, OSError):
                    self.ui_ready = False
                    self.ui_error = "菜单栏组件连接中断；状态服务仍在运行"
        if self.pending_notice and self.ui_ready and self.emit_notice(self.pending_notice):
            self.pending_notice = None
        saved = self.registry.saved()
        if saved != self.last_save:
            atomic_json(self.data / "slots.json", saved)
            # Use JSON round-trip to avoid retaining mutable references.
            self.last_save = json.loads(json.dumps(saved))
        # Identity hints are deliberately separate from the registry's visible
        # phases/numbering and read acknowledgements. No turns/requests/owners
        # survive a process restart. Bootstrap old installations on first use.
        if self.enabled:
            if self.last_recovery_save is None:
                for key, state in self.states.items():
                    if state.valid and key not in self.registry.hidden:
                        self.recovery.remember(key, state.metadata)
            recent = self.recovery.saved(self.registry.entries, self.registry.hidden)
            if recent != self.last_recovery_save:
                atomic_json(self.data / "recovery.json", recent)
                self.last_recovery_save = json.loads(json.dumps(recent))

    def emit_notice(self, notice):
        if not self.renderer or self.renderer.poll() is not None:
            return False
        try:
            self.renderer.stdin.write(json.dumps({"kind":"status_notice","notice":notice}, ensure_ascii=False) + "\n")
            self.renderer.stdin.flush()
            # Only this delivered card can authorize a notice click. It remains
            # routable if Codex has already read/removed the completed capsule.
            self.notice_target = ((notice["id"], notice["chat"]["id"])
                                  if notice.get("source") == "automatic" else None)
            self.notice_phase = notice["chat"].get("status") if notice.get("source") == "automatic" else None
            return True
        except (OSError, BrokenPipeError):
            self.ui_ready = False
            self.ui_error = "菜单栏组件连接中断；状态服务仍在运行"
            return False

    def consume_ui(self, message: dict, *, _probe=False) -> None:
        event, tid = message.get("event"), message.get("threadId")
        if self.resume_probe and not _probe and event not in ("ready","notice_shown","notice_closed"):
            self.finish_resume_probe(False,"user-interaction")
        if event == "ready":
            self.ui_ready, self.ui_error = True, None
            keys = {"source": "layoutSource", "version": "layoutVersion", "engine": "layoutEngine"}
            if all(isinstance(message.get(k), str) for k in keys.values()):
                self.ui_layout = {key: message[value] for key, value in keys.items()}
        elif event == "offline":
            self.ui_ready = False
            self.pending_notice = self.notice_target = self.notice_phase = None
            self.ui_error = "顶栏扩展未连接；请启用 Codex Signal GNOME 扩展"
        elif event in ("notification_enable", "notification_disable"):
            self.set_notification_state(message.get("status"), event == "notification_enable")
        elif event == "set_status_emoji":
            value = message.get("emoji")
            if isinstance(value, str) and 0 < len(value.encode("utf-8")) <= 128 and not any(ord(ch) < 32 or ch.isspace() for ch in value):
                self.status_emoji = value
                self.save_preferences();self.publish()
        elif event in ("compact_enable", "compact_disable"):
            self.compact_menu_bar = event == "compact_enable"
            self.save_preferences(); self.publish()
        elif event in ("project_enable", "project_disable"):
            self.set_project_updates(message.get("projectId"), event == "project_enable")
        elif event == "notice_open":
            target = (message.get("noticeId"), tid)
            if self.enabled and self.notice_target == target and isinstance(tid, str) and (url := chat_url(tid)):
                if self.open_chat_url(url):
                    self.notice_target = None  # A successful click is consumed once.
                    self.notice_receipts["opened"] += 1
        elif event in ("notice_shown", "notice_closed"):
            if event == "notice_closed" and self.notice_target and message.get("noticeId") == self.notice_target[0]:
                self.notice_target = None
            diagnostic = message.get("source") == "diagnostic"
            if event == "notice_shown":
                key = "diagnosticShown" if diagnostic else "shown"
                self.notice_receipts[key] += 1
            elif not diagnostic:
                self.notice_receipts["closed"] += 1
            fields = ("event", "noticeId", "source", "reason", "dwellMs", "uiLanguage", "becameKey", "activatedApplication")
            self.notice_receipts["lastReceipt"] = {k: message[k] for k in fields if k in message}
        elif event == "open" and isinstance(tid, str) and tid in self.registry.entries and (url := chat_url(tid)):
            # This path is reachable only from the native user's click, not MCP.
            self.open_chat_url(url)
        elif event == "seen" and tid in self.states:
            self.registry.mark_seen(self.states[tid])
        elif event == "reconnect":
            self.disconnect("正在重新连接")
            self.retry_at = 0
        elif event in ("enable", "disable", "reload"):
            self.control(event)

    def open_chat_url(self, url):
        command = "/usr/bin/open" if sys.platform == "darwin" else shutil.which("xdg-open")
        if not command:
            self.ui_error = "找不到聊天链接处理器；请配置 codex:// 桌面入口"
            return False
        try:
            if sys.platform.startswith("linux"):
                query = shutil.which("xdg-mime")
                if not query:
                    self.ui_error = "找不到聊天链接处理器；请配置 codex:// 桌面入口"
                    return False
                handler = subprocess.run([query, "query", "default", "x-scheme-handler/codex"],
                                         capture_output=True, text=True, timeout=2)
                if handler.returncode != 0 or not handler.stdout.strip():
                    self.ui_error = "找不到聊天链接处理器；请配置 codex:// 桌面入口"
                    return False
            subprocess.Popen([command, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (OSError, subprocess.TimeoutExpired):
            self.ui_error = "找不到聊天链接处理器；请配置 codex:// 桌面入口"
            return False

    def project_paused(self, key):
        pid = self.project_by_thread.get(key) or self.registry.entries.get(key, {}).get("project", {}).get("id")
        return pid in self.paused_projects

    def begin_snapshot_handoff(self):
        # Explicit master-on and an enabled payload startup revalidate only our
        # retained active IDs. This stage also covers the IPC handshake itself.
        deadline = time.monotonic() + RESUME_SNAPSHOT_WAIT
        self.resume_snapshots = {key: deadline for key in self.registry.entries if not self.project_paused(key)}
        self.resume_connecting = bool(self.resume_snapshots)

    def save_preferences(self):
        value = load_json(self.settings_path)
        value["enabled"] = self.enabled
        if self.paused_projects or "pausedProjects" in value:
            value["pausedProjects"] = self.paused_projects
        if self.status_emoji != "🔦" or "statusEmoji" in value:
            value["statusEmoji"] = self.status_emoji
        if self.compact_menu_bar or "compactMenuBar" in value:
            value["compactMenuBar"] = self.compact_menu_bar
        if self.notification_states != NoticeTracker.PHASES or "notificationStates" in value:
            value["notificationStates"] = sorted(self.notification_states)
        atomic_json(self.settings_path, value)

    def set_notification_state(self, phase, enabled):
        if phase not in NoticeTracker.PHASES:
            return
        if enabled:
            self.notification_states.add(phase)
        else:
            self.notification_states.discard(phase)
            if self.pending_notice and self.pending_notice["chat"]["status"] == phase:
                self.pending_notice = None
            if self.notice_phase == phase:
                self.notice_target = None
        self.save_preferences()
        self.publish()

    def set_project_updates(self, pid, enabled):
        if not isinstance(pid, str) or pid not in self.project_catalog:
            return
        if enabled == (pid not in self.paused_projects):
            return
        affected = {key for key in self.states if
                    key not in self.registry.hidden and
                    (self.project_by_thread.get(key) or self.registry.entries.get(key, {}).get("project", {}).get("id")) == pid}
        if enabled:
            self.paused_projects.pop(pid, None)
        else:
            self.paused_projects[pid] = self.project_catalog[pid]
            self.recovery.cancel(affected)
        self.notices.forget(affected)
        for key in affected:
            state = self.states[key]
            self.resume_snapshots.pop(key, None)
            if enabled:
                state.valid = False  # A fresh snapshot, not old paused state.
                if self.enabled and (self.connected or self.resume_connecting):
                    self.resume_snapshots[key] = time.monotonic() + RESUME_SNAPSHOT_WAIT
            if self.enabled and self.ipc:
                try:
                    if enabled:
                        self.expect_snapshot(key, baseline=True)
                    else:
                        self.ipc.follow(state.id, False, host_id=state.host_id)
                except (OSError, ConnectionError):
                    self.disconnect("状态接口暂不可用，正在重连")
        self.retry_snapshots()
        if not enabled:
            if self.pending_notice and self.pending_notice["project"]["id"] == pid:
                self.pending_notice = None
            if self.notice_target and self.notice_target[1] in affected:
                self.notice_target = None
        self.save_preferences()
        self.publish()

    def control(self, action: str) -> None:
        if self.resume_probe:
            self.finish_resume_probe(False,"plugin-control")
        if action == "reload":
            self.publish()  # Preserve the latest stable numbers/local seen state.
            self.events.put(("payload_handoff", self.reload_handoff()))
            # Run the normal finally block first. The small plugin host retains
            # stdin/stdout, queued requests and the lock while loading new code.
            self.reload_requested = True
            self.running = False
        elif action in ("enable", "disable"):
            self.enabled = action == "enable"
            self.save_preferences()
            self.disconnect("正在连接 Codex" if self.enabled else "监控已关闭")
            if self.enabled:
                self.begin_snapshot_handoff()
                self.retry_at = 0
            self.publish()

    def start_resume_probe(self, ticket, pid):
        group = next((g for g in self.last_status.get("projects",[]) if g["id"] == pid), None)
        if (os.environ.get("CODEX_MENU_STATUS_CAPTURE") != "1" or self.resume_probe or not self.enabled
                or not self.connected or not self.ui_ready or pid in self.paused_projects or not group
                or any(c["status"] == "unknown" for c in group["threads"])):
            return False
        self.resume_probe = ProjectResumeProbe(ticket,pid,time.monotonic())
        self.resume_probe.observe(self,self.last_status,time.monotonic())
        return True

    def tick_resume_probe(self, now):
        if self.resume_probe and (result := self.resume_probe.tick(self,now)) is not None:
            self.finish_resume_probe(*result)

    def finish_resume_probe(self, completed, reason):
        probe,self.resume_probe = self.resume_probe,None
        if not probe:return
        # Restore only the project preference owned by this exercise. Never
        # overwrite the settings file or undo an unrelated user's preference.
        if probe.project_id in self.paused_projects:
            self.consume_ui({"event":"project_enable","projectId":probe.project_id},_probe=True)
        probe.observe(self,self.last_status,time.monotonic())
        report={"requestId":probe.ticket,"projectId":probe.project_id,"completed":completed,"reason":reason,
                "input":"production-project-switch-events","transitions":probe.transitions,"samples":probe.samples,
                "restoredProjectEnabled":probe.project_id not in self.paused_projects,"nativeInspectionRequestId":probe.ticket}
        root=self.data/"render-check";root.mkdir(mode=0o700,parents=True,exist_ok=True)
        atomic_json(root/("project-resume-"+probe.ticket+".json"),report)
        if completed and self.renderer and self.renderer.poll() is None:
            try:
                self.renderer.stdin.write(json.dumps({"kind":"inspect_layout","requestId":probe.ticket})+"\n")
                self.renderer.stdin.flush()
            except (OSError,BrokenPipeError):pass

    def consume_commands(self) -> None:
        for value in pending(self.data):
            accepted = True
            if value["action"] == "exercise-project":
                accepted = self.start_resume_probe(value["id"],value.get("projectId"))
            elif value["action"] in ("compact-on", "compact-off"):
                self.consume_ui({"event":"compact_enable" if value["action"] == "compact-on" else "compact_disable"})
            elif value["action"] == "notice-demo":
                accepted = bool(self.enabled and self.ui_ready and os.environ.get("CODEX_MENU_STATUS_CAPTURE") == "1")
                if accepted:
                    accepted = self.emit_notice({"id":"diagnostic-"+value["id"],"source":"diagnostic","createdAt":time.time(),
                        "project":{"id":"notice-sample","name":"Codex","markerType":"icon","marker":"message-circle","threads":[]},
                        "chat":{"id":"notice-sample-chat","index":1,"title":text("noticeDemoTitle",self.language.language),"since":time.time(),"canMarkSeen":False,"status":"approval","detail":text("approval",self.language.language)}})
            elif value["action"] in ("inspect", "exercise", "inspect-settings", "choose-emoji", "exercise-menu"):
                accepted = bool(self.ui_ready and self.renderer and self.renderer.poll() is None
                                and os.environ.get("CODEX_MENU_STATUS_CAPTURE") == "1")
                if accepted:
                    try:
                        kind = {"inspect":"inspect_layout","exercise":"exercise_toggle","inspect-settings":"inspect_settings","choose-emoji":"choose_emoji","exercise-menu":"exercise_menu_layout"}[value["action"]]
                        self.renderer.stdin.write(json.dumps({"kind": kind, "requestId": value["id"]}) + "\n")
                        self.renderer.stdin.flush()
                    except (BrokenPipeError, OSError):
                        accepted = self.ui_ready = False
                        self.ui_error = "菜单栏组件连接中断；状态服务仍在运行"
            else:
                self.control(value["action"])
            receipts = self.data / "command-results"
            receipts.mkdir(mode=0o700, parents=True, exist_ok=True)
            write_json(receipts / (value["id"] + ".json"), {"id": value["id"], "accepted": accepted, "action": value["action"],
                "enabled": self.enabled, "nextVersion": latest_release(ROOT).name if value["action"] == "reload" else VERSION})
            if self.reload_requested:
                break

    def mcp(self, request: dict) -> None:
        method, request_id = request.get("method"), request.get("id")
        if request_id is None:
            return
        result, error = None, None
        if method == "initialize":
            result = {"protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "codex-menu-status", "version": VERSION}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{"name": "get_status", "description": "读取菜单栏插件当前连接和聊天状态；调用会确保插件自己的菜单栏组件正在运行。只返回元数据，不读取正文、不审批。",
                      "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                      "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
                      {"name": "control_monitor", "description": "仅控制本插件：enable 开启监控，disable 关闭监控但保留恢复入口，reload 重新加载本插件及已安装更新。不重启 Codex，不改变任何聊天。",
                       "inputSchema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["enable", "disable", "reload"]}}, "required": ["action"], "additionalProperties": False},
                       "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}}]}
        elif method == "tools/call" and request.get("params", {}).get("name") == "control_monitor":
            action = request.get("params", {}).get("arguments", {}).get("action")
            if action not in ("enable", "disable", "reload"):
                error = {"code": -32602, "message": "action 必须为 enable、disable 或 reload"}
            else:
                if self.primary:
                    self.control(action)
                    value = {"accepted": True, "action": action, "enabled": self.enabled}
                else:
                    value = {"queued": True, "action": action, "requestId": enqueue(self.data, action)}
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": value}
        elif method == "tools/call" and request.get("params", {}).get("name") == "get_status":
            status = dict(self.last_status if self.primary else load_json(self.data / "status.json"))
            if self.primary:
                status["diagnostics"] = {"observedThreads": len(self.states),
                    "subscriptions": len(self.ipc.following) if self.ipc else 0,
                    "messageCounts": self.event_counts}
            result = {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False)}], "structuredContent": status}
        elif method in ("resources/list", "resources/templates/list", "prompts/list"):
            result = {{"resources/list": "resources", "resources/templates/list": "resourceTemplates", "prompts/list": "prompts"}[method]: []}
        else:
            error = {"code": -32601, "message": "Method not found"}
        response = {"jsonrpc": "2.0", "id": request_id, "error" if error else "result": error or result}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def run(self, *, start_mcp_reader=True) -> None:
        if start_mcp_reader:
            self.start_reader("mcp", sys.stdin)
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: self.events.put(("shutdown", None)))
        poll_at, election_at = 0.0, 0.0
        try:
            while self.running:
                now = time.monotonic()
                if self.args.seconds and now - self.started >= self.args.seconds:
                    break
                if now >= election_at:
                    self.elect()
                    election_at = now + 1
                if self.primary:
                    self.consume_commands()
                    self.tick_resume_probe(time.monotonic())
                    if not self.running:
                        break
                    if self.enabled and self.ipc is None and now >= self.retry_at:
                        self.connect()
                    if self.ipc and not self.connected and self.handshake_deadline and now >= self.handshake_deadline:
                        self.disconnect("状态接口暂不可用，正在重连")
                    if now >= poll_at:
                        self.language.poll()
                        if self.enabled:
                            _, read_changed = self.metadata.poll()
                            self.refresh_pending |= read_changed
                            self.reconcile_availability()
                        poll_at = now + 0.5
                    if self.enabled and self.refresh_pending and now >= self.refresh_at:
                        self.refresh_tracked()
                        self.refresh_at, self.refresh_pending = now + 1, False
                    if self.enabled:
                        self.retry_snapshots()
                    self.publish()
                try:
                    kind, payload = self.events.get(timeout=0.15)
                except queue.Empty:
                    continue
                try:
                    if kind == "mcp":
                        self.mcp(payload)
                    elif kind in ("mcp_eof", "shutdown"):
                        self.running = False
                    elif kind == "ui_eof" and payload is self.renderer:
                        self.ui_ready = False
                        self.ui_error = "菜单栏组件未能保持运行；请从 Codex 桌面插件环境加载"
                        if self.renderer:
                            try:
                                self.renderer.wait(timeout=1)
                            except subprocess.TimeoutExpired:
                                self.renderer.terminate()
                                self.renderer.wait(timeout=3)
                        self.renderer = None
                    elif kind == "ui" and payload[0] is self.renderer:
                        self.consume_ui(payload[1])
                    elif kind == "ipc":
                        self.consume_ipc(*payload)
                    elif kind == "ipc_eof" and payload is self.ipc:
                        self.disconnect("与 Codex 连接中断")
                    elif kind == "payload_handoff":
                        self.consume_handoff(payload)
                except (OSError, ValueError, KeyError, TypeError):
                    if kind == "ipc":
                        self.disconnect("状态接口暂不可用，正在重连")
                finally:
                    payload = None
        finally:
            if self.resume_probe:
                self.finish_resume_probe(False, "plugin-shutdown")
            if self.ipc:
                self.ipc.close()
            if self.renderer and self.renderer.poll() is None:
                self.renderer.stdin.close()
                try:
                    self.renderer.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.renderer.terminate()
                    self.renderer.wait(timeout=3)
            if not self.reload_requested:
                self.lock.close()


def serve(args) -> None:
    plugin = Plugin(args)
    # One reader for the whole MCP lifetime. Requests arriving during a reload
    # stay queued, rather than being lost in an exec's discarded stdin buffer.
    plugin.start_reader("mcp", sys.stdin)
    while True:
        plugin.run(start_mcp_reader=False)
        if not plugin.reload_requested:
            break
        target = latest_release(ROOT)
        try:
            new_class = load_plugin_class(target)
            replacement = new_class(args, events=plugin.events, lock=plugin.lock)
        except (OSError, ImportError, SyntaxError, ValueError, AttributeError, TypeError):
            replacement = type(plugin)(args, events=plugin.events, lock=plugin.lock)
            replacement.update_error = "新版加载失败，已恢复先前插件版本"
        plugin = replacement


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ui", action="store_true", help="Protocol/integration test only")
    parser.add_argument("--seconds", type=int, default=0, help="Bounded diagnostic run; default follows MCP lifetime")
    serve(parser.parse_args())
