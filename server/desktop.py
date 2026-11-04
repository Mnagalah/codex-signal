"""Read-only, version-bound adapter for the existing desktop IPC router."""
from __future__ import annotations

import copy
import json
import pathlib
import socket
import struct
import uuid
if __package__:
    from .state import split_thread_key, thread_key
else:
    from state import split_thread_key, thread_key


class DesktopIPC:
    STREAM_VERSION = 11
    READ_VERSION = 3
    MAX_FRAME = 0x10000000

    def __init__(self, path: pathlib.Path):
        self.path, self.socket = path, None
        self.client_id = "initializing-client"
        self.following: set[tuple[str, str]] = set()

    def connect(self) -> None:
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(3)
        try:
            self.socket.connect(str(self.path))
            self.send({"type": "request", "requestId": str(uuid.uuid4()),
                       "sourceClientId": self.client_id, "method": "initialize", "version": 0,
                       "params": {"clientType": "codex-menu-status-plugin"}, "timeoutMs": 5000})
        except BaseException:
            self.socket.close()
            self.socket = None
            raise
        self.socket.settimeout(None)

    def send(self, message: dict) -> None:
        data = json.dumps(message, separators=(",", ":")).encode()
        if self.socket is None:
            raise ConnectionError("Desktop IPC is disconnected")
        self.socket.sendall(struct.pack("<I", len(data)) + data)

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
            data = self.socket.recv(262144)
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
            for host_id, thread_id in tuple(self.following):
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

    PROJECT_KEYS = ("local-projects", "remote-projects", "thread-project-assignments", "project-appearances")

    def __init__(self, path: pathlib.Path):
        self.path, self.signature = path, None
        self.projects, self.assignments, self.appearances = {}, {}, {}
        self.remote_projects = []
        self.read_state: dict = {}
        self.error: str | None = None

    def poll(self) -> tuple[bool, bool]:
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if signature == self.signature:
                return False, False
            raw = json.loads(self.path.read_text())
            project_values = [raw.get(k, [] if k == "remote-projects" else {}) for k in self.PROJECT_KEYS]
            # These are local UI read-state keys. Values stay in memory; identity
            # context keys are not interpreted, copied to evidence, or logged.
            reads = {k: v for k, v in raw.items() if "thread-read-state" in k}
            legacy = raw.get("electron-persisted-atom-state", {}).get("unread-thread-ids-by-host-v1")
            if legacy is not None:
                reads["legacy-read-state"] = legacy
            project_changed = project_values != [self.projects, self.remote_projects, self.assignments, self.appearances]
            read_changed = self.signature is not None and reads != self.read_state
            self.projects, self.remote_projects, self.assignments, self.appearances = project_values
            self.read_state = copy.deepcopy(reads)
            self.signature, self.error = signature, None
            return project_changed, read_changed
        except (OSError, ValueError, TypeError):
            self.error = "无法读取项目/已读元数据"
            return False, False

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
                assigned = assignment.get("projectId") if isinstance(assignment, dict) and assignment.get("projectKind") == "remote" else None
                project = next((p for p in candidates if p.get("id") == assigned), None) if assigned else None
                if project is None and state is not None and state.metadata.get("workspaceKind") == "project":
                    cwd = state.metadata.get("cwd")
                    # Match an actual registered remote root, not its basename.
                    # Host identity is part of the match; longest parent wins.
                    matches = []
                    if isinstance(cwd, str):
                        cwd = str(pathlib.PurePosixPath(cwd))
                        for p in candidates:
                            path = p.get("remotePath")
                            if isinstance(path, str):
                                path = str(pathlib.PurePosixPath(path)).rstrip("/") or "/"
                                if cwd == path or cwd.startswith(path.rstrip("/") + "/"):
                                    matches.append((len(path), p))
                    project = max(matches, key=lambda x: x[0])[1] if matches else None
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
