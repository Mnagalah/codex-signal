"""Read-only local lifecycle reconciliation, scoped to IDs Signal already knows."""
from __future__ import annotations

import sqlite3

if __package__:
    from .state import split_thread_key
else:
    from state import split_thread_key


class LocalThreadAvailability:
    def __init__(self, path):
        self.path = path.resolve()
        self.persisted = set()
        self.available = False

    def poll(self, states, entries, hidden):
        # A remote ID missing from this machine's database says nothing about
        # that remote chat. Cloud-backed local summaries are not local rows either.
        keys = set()
        for key in states.keys() | entries.keys() | hidden.keys():
            if split_thread_key(key)[0] != 'local':
                continue
            metadata = states[key].metadata if key in states else {}
            if (metadata.get('threadSource') != 'aeon' and not metadata.get('ephemeral')
                    and not metadata.get('parentThreadId')):
                keys.add(key)
        if not keys:
            return {}
        result = {}
        try:
            with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=0.1) as db:
                rows = {key: db.execute('SELECT archived FROM threads WHERE id=?',
                        (split_thread_key(key)[1],)).fetchone() for key in keys}
            for key, row in rows.items():
                if row is not None:
                    self.persisted.add(key)
                    result[key] = 'archived' if row[0] else 'active'
                elif key in self.persisted or entries.get(key, {}).get('phase') in ('completed', 'failed', 'stopped'):
                    # Existing persisted local chats, including legacy finished
                    # records, must have a local row. New unsaved chats do not.
                    result[key] = 'deleted'
            self.available = True
        except (OSError, sqlite3.Error):
            # A missing/locked/changed database is not a successful empty query.
            self.available = False
        return result
