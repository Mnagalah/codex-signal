"""Desktop-owned unread membership, independent of task-stream freshness."""
from __future__ import annotations

import re

if __package__:
    from .state import split_thread_key, thread_key
else:
    from state import split_thread_key, thread_key

UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


class UnreadProjection:
    def __init__(self):
        self.scopes = {}
        self.added = set()
        self.overrides = {}

    def sync(self, scopes):
        if scopes == self.scopes:
            return
        # A change of account/host configuration is not an unread edge.
        # Remember an explicit new membership until the stream catches up or
        # the user acknowledges it in Signal.
        self.added = {key for key in self.added
                      if self._same_scope(key, scopes) and self._listed(key, scopes)}
        for host, (scope, ids) in scopes.items():
            previous = self.scopes.get(host)
            if previous and previous[0] == scope:
                self.added.update(thread_key(host, tid) for tid in ids - previous[1] if UUID.fullmatch(tid))
        # An explicit IPC edge can precede the persisted snapshot. Keep it
        # over unrelated writes, but retire it when its own membership changes.
        self.overrides = {
            key: bit for key, bit in self.overrides.items()
            if self._same_scope(key, scopes) and self._listed(key, scopes) == self._listed(key, self.scopes)
        }
        self.scopes = scopes

    def _same_scope(self, key, scopes):
        host, _ = split_thread_key(key)
        return host in self.scopes and host in scopes and self.scopes[host][0] == scopes[host][0]

    @staticmethod
    def _listed(key, scopes):
        host, tid = split_thread_key(key)
        return host in scopes and tid in scopes[host][1]

    def membership(self, key):
        host, _ = split_thread_key(key)
        return self.overrides.get(key, self._listed(key, self.scopes)) if host in self.scopes else None

    def keys(self):
        return {thread_key(host, tid) for host, (_, ids) in self.scopes.items()
                for tid in ids if UUID.fullmatch(tid) and self.overrides.get(thread_key(host, tid), True)
                } | {key for key, bit in self.overrides.items() if bit}

    def observe(self, key, unread):
        host, _ = split_thread_key(key)
        if host in self.scopes:
            if unread == self._listed(key, self.scopes):
                self.overrides.pop(key, None)
            else:
                self.overrides[key] = unread
        if not unread:
            self.added.discard(key)

    def dismiss(self, key):
        self.added.discard(key)

    def take_unread_edge(self, key):
        if key not in self.added:
            return False
        self.added.remove(key)
        return True
