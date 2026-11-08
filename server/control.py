"""Control only this plugin; no Codex process control or global config mutation."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import time
import uuid

ACTIONS = {"enable", "disable", "reload", "check", "inspect", "exercise", "notice-demo", "inspect-settings", "choose-emoji", "exercise-menu", "exercise-project", "compact-on", "compact-off"}
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


if __package__:
    from .runtime_paths import data_directory
else:
    from runtime_paths import data_directory


def write_json(path: pathlib.Path, value: dict) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(temp, path)


def valid_project_id(value):
    return isinstance(value,str) and 0<len(value.encode('utf-8'))<=256 and not any(ord(c)<32 for c in value)


def enqueue(root: pathlib.Path, action: str, *, project_id=None) -> str:
    if action not in ACTIONS:
        raise ValueError("Unknown plugin action")
    if action == "exercise-project":
        if not valid_project_id(project_id): raise ValueError("exercise-project requires a project ID")
    elif project_id is not None:
        raise ValueError("project ID is only valid for exercise-project")
    inbox = root / "commands"
    inbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    ticket = uuid.uuid4().hex
    write_json(inbox / (ticket + ".json"), {"id": ticket, "action": action, "createdAtNs": time.time_ns()} | ({"projectId":project_id} if project_id is not None else {}))
    return ticket


def pending(root: pathlib.Path):
    inbox = root / "commands"
    if not inbox.is_dir():
        return
    requests = []
    for path in inbox.glob("*.json"):
        # Each request is independent; concurrent clients cannot overwrite one
        # another. The payload is an enum, never a command, filename or URL.
        if not re.fullmatch(r"[0-9a-f]{32}", path.stem) or path.is_symlink():
            continue
        try:
            if path.stat().st_size > 512:
                continue
            value = json.loads(path.read_text())
            if value.get("id") != path.stem or value.get("action") not in ACTIONS:
                continue
            if value["action"] == "exercise-project" and not valid_project_id(value.get("projectId")):
                continue
            stamp = value.get("createdAtNs")
            # Legacy requests retain their filesystem ordering. New requests
            # carry an explicit timestamp: rapid writes can share one FS tick.
            if not isinstance(stamp, int) or isinstance(stamp, bool):
                stamp = path.stat().st_mtime_ns
            requests.append((stamp, path.name, path, value))
        except (OSError, ValueError, AttributeError):
            continue
    for _, _, path, value in sorted(requests)[:16]:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        yield value


def latest_release(current: pathlib.Path) -> pathlib.Path:
    """Resolve updates only within this plugin's existing managed version cache."""
    if not VERSION.fullmatch(current.name) or current.parent.name != "codex-menu-status":
        return current
    releases = []
    for candidate in current.parent.iterdir():
        if not VERSION.fullmatch(candidate.name) or candidate.is_symlink() or not candidate.is_dir():
            continue
        try:
            manifest = json.loads((candidate / "plugin.json").read_text())
            if manifest.get("name") != "codex-menu-status" or manifest.get("version") != candidate.name:
                continue
            if not (candidate / "server/main.py").is_file() or not (candidate / "bin/codex-menu-bar").is_file():
                continue
            releases.append((tuple(map(int, candidate.name.split("."))), candidate))
        except (OSError, ValueError):
            continue
    return max(releases, default=((), current))[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="仅控制 Codex 对话状态栏，不重启 Codex")
    parser.add_argument("action", choices=["on", "off", "reload", "status", "inspect", "exercise", "notice-demo", "inspect-settings", "choose-emoji", "exercise-menu", "exercise-project", "compact-on", "compact-off"])
    parser.add_argument("--project-id")
    args = parser.parse_args()
    if (args.action == "exercise-project") != (args.project_id is not None):
        parser.error("--project-id is required only for exercise-project")
    root = data_directory()
    if args.action == "status":
        print((root / "status.json").read_text())
        return
    action = {"on": "enable", "off": "disable"}.get(args.action, args.action)
    ticket = enqueue(root, action, project_id=args.project_id)
    deadline = time.monotonic() + 6
    receipt = root / "command-results" / (ticket + ".json")
    while time.monotonic() < deadline:
        if receipt.is_file():
            print(receipt.read_text())
            receipt.unlink()
            return
        time.sleep(0.1)
    # A timeout cannot distinguish queued, applied, or claimed-before-crash.
    raise SystemExit("插件尚未确认此请求。请求可能仍在排队，也可能已处理但未返回确认；请检查插件状态后重试，无需重启 Codex。")


if __name__ == "__main__":
    main()
