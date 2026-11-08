import json
import pathlib
import struct
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server"))
from desktop import DesktopIPC, DesktopMetadata


class FakeSocket:
    def __init__(self, chunks=()):
        self.chunks = iter(chunks)
    def recv(self, _):
        return next(self.chunks, b"")


def frame(value):
    b = json.dumps(value).encode()
    return struct.pack("<I", len(b)) + b


class AdapterTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames(self):
        data = frame({"a": 1}) + frame({"b": 2})
        ipc = DesktopIPC(pathlib.Path("unused"))
        ipc.socket = FakeSocket([data[:2], data[2:8], data[8:]])
        from unittest.mock import patch
        with patch('desktop.select.select', return_value=([ipc.socket], [], [])):
            self.assertEqual(list(ipc.messages()), [{"a": 1}, {"b": 2}])

    def test_no_execution_or_owner_capability(self):
        ipc = DesktopIPC(pathlib.Path("unused"))
        left, right = socket.socketpair()
        self.addCleanup(left.close); self.addCleanup(right.close)
        left.setblocking(False); ipc.socket = left
        ipc.acknowledge_protocol({"type": "response", "method": "initialize", "resultType": "success", "result": {"clientId": "own-client"}})
        ipc.acknowledge_protocol({"type": "client-discovery-request", "requestId": "r"})
        ipc.follow("thread")
        ipc.follow("thread", False)
        left.shutdown(socket.SHUT_WR)
        received = DesktopIPC(pathlib.Path("unused")); received.socket = right
        right.setblocking(False)
        messages = list(received.messages())
        self.assertEqual(messages[0]["response"], {"canHandle": False})
        self.assertEqual([m.get("method") for m in messages[1:]], ["thread-stream-following-changed"] * 2)
        self.assertTrue(all(m.get("sourceClientId") == "own-client" for m in messages[1:]))

    def test_project_name_is_not_directory_and_read_changes_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "state.json"
            data = {"local-projects": {"p": {"name": "真正的项目名", "rootPaths": ["/different/folder"]}},
                    "thread-project-assignments": {"thread": {"projectKind": "local", "projectId": "p"}},
                    "project-appearances": {"p": {"marker": {"kind": "emoji", "emoji": "📚"}}},
                    "electron-thread-read-state-v1": {"version": 1, "unreadByIdentity": {"opaque": {"not-local": ["thread"]}}}}
            path.write_text(json.dumps(data))
            metadata = DesktopMetadata(path)
            self.assertEqual(metadata.poll(), (True, False))
            identity = metadata.identities(["thread"])["thread"]
            self.assertEqual(identity["name"], "真正的项目名")
            self.assertEqual(identity["marker"], "📚")
            # Atomic replacement, as the desktop does. Never interpret identity
            # buckets or infer read from absence: only signal reconciliation.
            data["electron-thread-read-state-v1"]["unreadByIdentity"]["opaque"]["not-local"] = []
            replacement = path.with_suffix(".new")
            replacement.write_text(json.dumps(data))
            replacement.replace(path)
            self.assertEqual(metadata.poll(), (False, True))


if __name__ == "__main__":
    unittest.main()
