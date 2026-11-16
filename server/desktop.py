"""Read-only, version-bound adapter for the existing desktop IPC router."""
from __future__ import annotations

import copy
import json
import pathlib
import re
import socket
import select
import struct
import uuid
if __package__:
    from .state import split_thread_key, thread_key
    from .transport import write_all
else:
    from state import split_thread_key, thread_key
    from transport import write_all


class DesktopIPC:
    STREAM_VERSIONS = (11, 13)
    READ_VERSION = 3
    ARCHIVE_VERSION = 2
    UNARCHIVE_VERSION = 1
    MAX_FRAME = 0x10000000
    SEND_TIMEOUT = 1.0

    def __init__(self, path: pathlib.Path):
        self.path, self.socket = path, None
        self.client_id = "initializing-client"
        self.write_failed = False
        self.following: set[tuple[str, str]] = set()

    def connect(self) -> None:
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.write_failed = False
        self.socket.settimeout(3)
        try:
            self.socket.connect(str(self.path))
            self.socket.setblocking(False)
            self.send({"type": "request", "requestId": str(uuid.uuid4()),
                       "sourceClientId": self.client_id, "method": "initialize", "version": 0,
                       "params": {"clientType": "codex-menu-status-plugin"}, "timeoutMs": 5000})
        except BaseException:
            self.socket.close()
            self.socket = None
            raise

    def send(self, message: dict) -> None:
        data = json.dumps(message, separators=(",", ":")).encode()
        if self.socket is None or self.write_failed:
            raise ConnectionError("Desktop IPC is disconnected")
        # Reads have no idle deadline; writes must not freeze controls/recovery.
        try:
            write_all(self.socket.fileno(), struct.pack("<I", len(data)) + data,
                      timeout=self.SEND_TIMEOUT)
        except OSError:
            self.write_failed = True  # A partial frame cannot be retried in place.
            raise

    def follow(self, thread_id: str, enabled: bool = True, *, host_id: str = "local") -> None:
        if self.client_id == "initializing-client":
            return
        self.send({"type": "broadcast", "method": "thread-stream-following-changed",
                   "sourceClientId": self.client_id, "version": 1,
                   "params": {"hostId": host_id, "conversationId": thread_id, "following": enabled}})
        if enabled:
            self.following.add((host_id, thread_id))
        else:
            self.following.discard((host_id, thread_id))

    def messages(self):
        buffer = bytearray()
        while self.socket is not None:
            sock = self.socket
            if not select.select([sock], [], [], 0.5)[0]:
                continue  # Idle is not EOF and has no receive deadline.
            try:
                data = sock.recv(262144)
            except (BlockingIOError, InterruptedError):
                continue
            if not data:
                return
            buffer.extend(data)
            data = b""
            while len(buffer) >= 4:
                length = struct.unpack_from("<I", buffer)[0]
                if not 0 < length <= self.MAX_FRAME:
                    raise ValueError("Invalid desktop IPC frame")
                if len(buffer) < length + 4:
                    break
                payload = bytes(buffer[4:length + 4])
                del buffer[:length + 4]
                decoded = json.loads(payload)
                del payload
                yield decoded
                decoded = None

    def acknowledge_protocol(self, message: dict) -> bool:
        """Only acknowledge initialization/discovery; never handle thread actions."""
        kind = message.get("type")
        if kind == "response" and message.get("method") == "initialize":
            if message.get("resultType") != "success":
                raise ConnectionError("Desktop rejected plugin initialization")
            self.client_id = message["result"]["clientId"]
            return True
        if kind == "client-discovery-request":
            self.send({"type": "client-discovery-response", "requestId": message["requestId"],
                       "response": {"canHandle": False}})
        elif kind == "request":
            self.send({"type": "response", "requestId": message["requestId"],
                       "resultType": "error", "error": "method-not-supported"})
        return False

    def close(self) -> None:
        if self.socket is not None:
            for host_id, thread_id in (() if self.write_failed else tuple(self.following)):
                try:
                    self.follow(thread_id, False, host_id=host_id)
                except OSError:
                    break
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        self.socket = None
        self.following.clear()


class DesktopMetadata:
    """Read only project identity and read-state metadata, never credentials."""

    PROJECT_KEYS = ("local-projects", "remote-projects", "thread-project-assignments", "project-appearances",
                    "projectless-thread-ids")
    READ_STORE = "electron-thread-read-state-v1"

    def __init__(self, path: pathlib.Path):
        self.path, self.signature = path, None
        self.projects, self.assignments, self.appearances = {}, {}, {}
        self.remote_projects = []
        self.projectless = []
        self.remote_cwds = {}
        self.read_state: dict = {}
        self.error: str | None = None

    def unread_scopes(self) -> dict:
        """Known v1 format: one identity, one unambiguous bucket per host.

        The opaque suffix identifies a host configuration, not a thread. Never
        union different accounts or two configurations sharing a host alias.
        """
        store = self.read_state.get(self.READ_STORE)
        if not isinstance(store, dict) or type(store.get("version")) is not int or store["version"] != 1:
            return {}
        accounts = store.get("unreadByIdentity")
        if not isinstance(accounts, dict) or len(accounts) != 1:
            return {}
        identity, buckets = next(iter(accounts.items()))
        if not isinstance(buckets, dict) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            return {}
        scopes = {}
        seen = set()
        for scope, ids in buckets.items():
            host, separator, generation = scope.rpartition(":")
            if not separator or not host or not re.fullmatch(r"[0-9a-f]{64}", generation):
                continue
            if host in seen:
                scopes.pop(host, None)
                continue
            seen.add(host)
            if isinstance(ids, list) and all(isinstance(tid, str) for tid in ids):
                scopes[host] = ((identity, scope), frozenset(ids))
        return scopes

    def poll(self) -> tuple[bool, bool]:
        try:
            stat = self.path.stat()
            signature = (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
            if signature == self.signature:
                return False, False
            raw = json.loads(self.path.read_text())
            if not isinstance(raw, dict):
                raise ValueError("Invalid desktop state")
            default = ({}, [], {}, {}, [])
            project_values = [raw.get(k, empty) for k, empty in zip(self.PROJECT_KEYS, default)]
            project_values = [value if type(value) is type(empty) else empty
                              for value, empty in zip(project_values, default)]
            # Keep read-state metadata in memory only. Other revisions remain
            # change signals for stream refresh, not sources of chat admission.
            reads = {k: v for k, v in raw.items() if "thread-read-state" in k}
            legacy_state = raw.get("electron-persisted-atom-state")
            legacy = legacy_state.get("unread-thread-ids-by-host-v1") if isinstance(legacy_state, dict) else None
            if legacy is not None:
                reads["legacy-read-state"] = legacy
            project_changed = project_values != [self.projects, self.remote_projects, self.assignments, self.appearances, self.projectless]
            read_changed = self.signature is not None and reads != self.read_state
            self.projects, self.remote_projects, self.assignments, self.appearances, self.projectless = project_values
            self.read_state = copy.deepcopy(reads)
            self.signature, self.error = signature, None
            return project_changed, read_changed
        except (OSError, ValueError, TypeError):
            self.error = "无法读取项目/已读元数据"
            return False, False

    @staticmethod
    def remote_root(projects, cwd):
        if not isinstance(cwd, str):
            return None
        cwd = pathlib.PurePosixPath(cwd)
        if not cwd.is_absolute() or ".." in cwd.parts:
            return None
        matches = []
        for project in projects:
            root = project.get("remotePath")
            if isinstance(root, str):
                root = pathlib.PurePosixPath(root)
                if root.is_absolute() and ".." not in root.parts and cwd.is_relative_to(root):
                    matches.append((len(root.parts), project))
        if not matches:
            return None
        depth = max(depth for depth, _ in matches)
        deepest = [project for size, project in matches if size == depth]
        return deepest[0] if len(deepest) == 1 else None

    def identities(self, thread_ids) -> dict:
        result = {}
        for key in thread_ids:
            host_id, tid = split_thread_key(key)
            state = thread_ids.get(key) if isinstance(thread_ids, dict) else None
            assignment = self.assignments.get(tid)
            if host_id == "local":
                if not isinstance(assignment, dict) or assignment.get("projectKind") != "local":
                    continue
                pid = assignment.get("projectId")
                project = self.projects.get(pid, {})
                name = project.get("name")
            else:
                candidates = [p for p in self.remote_projects if isinstance(p, dict) and p.get("hostId") == host_id]
                meta = state.metadata if state is not None else {}
                assigned = (assignment.get("projectId")
                            if isinstance(assignment, dict) and assignment.get("projectKind") == "remote"
                            and assignment.get("hostId", host_id) == host_id else None)
                project = next((p for p in candidates if p.get("id") == assigned), None) if assigned else None
                if project is None and tid not in self.projectless and meta.get("workspaceKind") != "projectless":
                    pid = meta.get("projectId")
                    project = next((p for p in candidates if p.get("id") == pid), None) if pid else None
                    if project is None:
                        # The stream wins over the catalog. For a cold unread
                        # chat, the desktop's indexed cwd can stand in for it.
                        project = self.remote_root(candidates, meta.get("cwd") or self.remote_cwds.get(key))
                if project is None:
                    continue
                pid, name = project.get("id"), project.get("label")
            if not isinstance(name, str) or not name:
                continue
            marker = self.appearances.get(pid, {}).get("marker") or {"kind": "icon", "icon": "folder"}
            marker_type = marker.get("kind", "icon")
            result[key] = {"id": thread_key(host_id, pid), "name": name, "markerType": marker_type,
                           "marker": marker.get("emoji" if marker_type == "emoji" else "icon", "folder")}
            if host_id != "local":
                result[key].update({"projectId": pid, "hostId": host_id, "hostLabel": project.get("hostDisplayName")})
        return result
