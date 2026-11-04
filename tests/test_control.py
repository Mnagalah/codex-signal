import argparse
import json
import os
import pathlib
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SERVER = pathlib.Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER))
from control import enqueue, latest_release, pending, write_json
from main import Plugin, VERSION, load_plugin_class


class ControlTests(unittest.TestCase):
    def test_queue_preserves_independent_requests_and_has_no_command_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            one = enqueue(root, "disable")
            two = enqueue(root, "enable")
            self.assertNotEqual(one, two)
            self.assertEqual([x["action"] for x in pending(root)], ["disable", "enable"])
            self.assertEqual(list(pending(root)), [])
            with self.assertRaises(ValueError):
                enqueue(root, "/bin/sh")

    def test_only_complete_versions_of_this_same_plugin_are_update_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "codex-menu-status"
            for version, name, complete in [("0.1.6", "codex-menu-status", True), ("0.1.7", "codex-menu-status", True),
                                             ("9.0.0", "other-plugin", True), ("8.0.0", "codex-menu-status", False)]:
                release = base / version
                (release / "server").mkdir(parents=True)
                (release / "bin").mkdir()
                (release / "plugin.json").write_text(json.dumps({"name": name, "version": version}))
                (release / "server/main.py").write_text("# example")
                if complete:
                    (release / "bin/codex-menu-bar").write_text("example")
                    (release / "server/linux_renderer.py").write_text("# Linux renderer fixture")
            (base / "10.0.0").symlink_to(base / "0.1.7", target_is_directory=True)
            self.assertEqual(latest_release(base / "0.1.6"), base / "0.1.7")

    def test_switch_persists_without_clearing_slots_or_requesting_chat_operations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_MENU_STATUS_DATA": tmp}):
            plugin = Plugin(argparse.Namespace(no_ui=True, seconds=0))
            plugin.primary = True
            plugin.control("disable")
            self.assertFalse(plugin.enabled)
            self.assertEqual(plugin.last_status["projects"], [])
            self.assertEqual(plugin.last_status["detail"], "状态更新已暂停")
            saved = (pathlib.Path(tmp) / "slots.json").read_text()
            plugin.control("enable")
            self.assertTrue(plugin.enabled)
            self.assertEqual((pathlib.Path(tmp) / "slots.json").read_text(), saved)
            self.assertEqual(json.loads((pathlib.Path(tmp) / "settings.json").read_text()), {"enabled": True})
            plugin.lock.close()

    def test_payload_import_uses_an_isolated_namespace_and_keeps_same_transport_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_MENU_STATUS_DATA": tmp}):
            old = Plugin(argparse.Namespace(no_ui=True, seconds=0))
            cls = load_plugin_class(SERVER.parent)
            new = cls(old.args, events=old.events, lock=old.lock)
            self.assertIs(new.events, old.events)
            self.assertIs(new.lock, old.lock)
            self.assertNotEqual(cls.__module__, Plugin.__module__)
            old.lock.close()

    def test_stdio_connection_and_pipelined_requests_survive_plugin_only_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write_json(root / "settings.json", {"enabled": False})
            env = dict(os.environ, CODEX_MENU_STATUS_DATA=tmp)
            process = subprocess.Popen([sys.executable, str(SERVER / "main.py"), "--no-ui"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
            def send(value):
                process.stdin.write(json.dumps(value) + "\n")
                process.stdin.flush()
            def read():
                # Wait on the fd, then readline one response. Each exchange has
                # one line, except the deliberately pipelined reload pair below.
                self.assertTrue(select.select([process.stdout], [], [], 5)[0], "MCP response timeout")
                return json.loads(process.stdout.readline())
            try:
                send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                self.assertEqual(read()["result"]["serverInfo"]["version"], VERSION)
                send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                self.assertIn("control_monitor", [x["name"] for x in read()["result"]["tools"]])
                # Both requests arrive together. The persistent reader must keep
                # request 4, even if it read that line before reload begins.
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                    "name": "control_monitor", "arguments": {"action": "reload"}}}) + "\n" + json.dumps({
                    "jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_status"}}) + "\n")
                process.stdin.flush()
                first = read()
                self.assertEqual(first["id"], 3)
                # TextIO may already have buffered the next line. Read it directly;
                # the first select timeout already guards the transition startup.
                second = json.loads(process.stdout.readline())
                self.assertEqual(second["id"], 4)
                self.assertFalse(second["result"]["structuredContent"]["enabled"])
                self.assertIsNone(process.poll())
                process.stdin.close()
                process.wait(timeout=5)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()


    def check_reload_release(self, broken):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            cache = root / "codex-menu-status"
            for version in ["0.1.6", "0.1.7"]:
                release = cache / version
                shutil.copytree(SERVER, release / "server", ignore=shutil.ignore_patterns("__pycache__"))
                shutil.copy2(SERVER.parent / "codex-status-layout.html", release / "codex-status-layout.html")
                (release / "bin").mkdir()
                (release / "bin/codex-menu-bar").write_text("not used in no-ui test")
                (release / "plugin.json").write_text(json.dumps({"name": "codex-menu-status", "version": version}))
                main = release / "server/main.py"
                main.write_text(main.read_text().replace('VERSION = "' + VERSION + '"', 'VERSION = "' + version + '"'))
            if broken:
                (cache / "0.1.7/server/main.py").write_text("invalid python syntax !!!")
            data = root / "data"
            data.mkdir()
            write_json(data / "settings.json", {"enabled": False})
            env = dict(os.environ, CODEX_MENU_STATUS_DATA=str(data))
            process = subprocess.Popen([sys.executable, str(cache / "0.1.6/server/main.py"), "--no-ui"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            try:
                values = [
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "control_monitor", "arguments": {"action": "reload"}}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_status"}}]
                process.stdin.write("".join(json.dumps(x) + "\n" for x in values).encode())
                process.stdin.flush()
                buffer = b""
                deadline = time.monotonic() + 5
                while buffer.count(b"\n") < 2 and time.monotonic() < deadline:
                    if select.select([process.stdout], [], [], 0.2)[0]:
                        buffer += os.read(process.stdout.fileno(), 65536)
                responses = [json.loads(x) for x in buffer.splitlines()]
                self.assertEqual([x["id"] for x in responses], [1, 2])
                status = responses[1]["result"]["structuredContent"]
                self.assertEqual(status["pluginVersion"], "0.1.6" if broken else "0.1.7")
                self.assertEqual("updateError" in status, broken)
                self.assertFalse(status["enabled"])
                process.stdin.close()
                process.wait(timeout=5)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()

    def test_reload_adopts_new_installed_payload_without_reconnecting_mcp(self):
        self.check_reload_release(False)

    def test_invalid_update_restores_previous_plugin_and_reports_failure(self):
        self.check_reload_release(True)


if __name__ == "__main__":
    unittest.main()
