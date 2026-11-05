"""Recent identities and bounded snapshot retry; never persists task truth."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import time

if __package__:
    from .state import split_thread_key
else:
    from state import split_thread_key

CONTEXT = ('workspaceKind', 'cwd', 'projectId')
UUID = re.compile(r'^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')


@dataclass
class AwaitingSnapshot:
    started: float
    next_at: float
    attempts: int = 0
    required: bool = False
    baseline: bool = False


class Recovery:
    # Visible IDs are protected separately. This bounds only inactive hints,
    # not the number of real tasks or acknowledgements preserved by Signal.
    RECENT_LIMIT = 128
    SYNC_WAIT = 5.0
    DISCOVERY_WAIT = 1.0

    def __init__(self):
        self.recent: dict[str, dict] = {}
        self.pending: dict[str, AwaitingSnapshot] = {}
        self.offline_owners: set[str] = set()
        self.discovery_until = 0.0

    def load(self, saved):
        records = saved.get('threads', {})
        if not isinstance(records, dict):
            return
        for key, record in records.items():
            if not isinstance(key, str) or not isinstance(record, dict):
                continue
            host, tid = split_thread_key(key)
            seen = record.get('lastSeen')
            if (not host or len(host) > 1024 or not UUID.fullmatch(tid)
                    or not isinstance(seen, (int, float)) or not math.isfinite(seen)):
                continue
            self.recent[key] = {'lastSeen': seen,
                'projectMetadata': self.context(record.get('projectMetadata', {}))}

    @staticmethod
    def context(metadata):
        return {k: metadata[k] for k in CONTEXT if isinstance(metadata, dict)
                and isinstance(metadata.get(k), str)}

    def remember(self, key, metadata):
        if metadata.get('ephemeral') or metadata.get('parentThreadId'):
            self.recent.pop(key, None)
            return
        now = time.time()
        context = self.context(metadata)
        old = self.recent.get(key)
        if old is None or old['projectMetadata'] != context or now - old['lastSeen'] >= 3600:
            self.recent[key] = {'lastSeen': now, 'projectMetadata': context}

    def saved(self, visible=(), hidden=()):
        for key in hidden:
            self.recent.pop(key, None)
        protected = set(visible)
        inactive = sorted((key for key in self.recent if key not in protected),
                          key=lambda key: self.recent[key]['lastSeen'], reverse=True)
        for key in inactive[self.RECENT_LIMIT:]:
            self.recent.pop(key, None)
        return {'version': 1, 'threads': self.recent}

    def expect(self, key, *, required=False, baseline=False, now=None):
        now = time.monotonic() if now is None else now
        item = self.pending.setdefault(key, AwaitingSnapshot(now, now))
        item.required |= required
        item.baseline |= baseline

    def cancel(self, keys):
        for key in keys:
            self.pending.pop(key, None)

    def received(self, key):
        item = self.pending.pop(key, None)
        return item is not None and item.baseline

    def due(self, *, now=None, limit=8):
        now = time.monotonic() if now is None else now
        keys = [key for key, item in self.pending.items() if item.next_at <= now][:limit]
        for key in keys:
            item = self.pending[key]
            item.next_at = now + min(30, 2 ** min(item.attempts, 5))
            item.attempts += 1
        return keys

    def health(self, now=None):
        now = time.monotonic() if now is None else now
        required = [item for item in self.pending.values() if item.required]
        if any(now - item.started >= self.SYNC_WAIT for item in required):
            return 'unavailable'
        if required or now < self.discovery_until:
            return 'syncing'
        return None
