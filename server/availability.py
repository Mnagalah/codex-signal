"""Read-only local chat lookups scoped to observed and explicitly unread IDs."""
from __future__ import annotations

from contextlib import closing
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

    def unread_metadata(self, ids):
        """Resolve only explicitly unread local IDs, without reading history."""
        if not ids:
            return {}
        try:
            with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=0.1)) as db:
                columns = {row[1] for row in db.execute('PRAGMA table_info(threads)')}
                optional = [name for name in ('thread_source', 'attached_thread_parent_id') if name in columns]
                select_columns = ', '.join(['title', 'cwd'] + optional)
                result = {}
                for tid in ids:
                    row = db.execute(f'SELECT {select_columns} FROM threads WHERE id=? AND archived=0', (tid,)).fetchone()
                    if row is None:
                        continue
                    values = dict(zip(['title', 'cwd'] + optional, row))
                    if values.get('thread_source') != 'aeon' and not values.get('attached_thread_parent_id'):
                        result[tid] = {key: values[key] for key in ('title', 'cwd') if isinstance(values[key], str)}
                return result
        except (OSError, sqlite3.Error):
            return {}

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
            with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=0.1)) as db:
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


class RemoteThreadCatalog:
    """Optional grouping hints from the desktop's index, not a discovery source."""

    def __init__(self, path):
        self.path = path.resolve()
        self.wal = self.path.with_name(self.path.name + "-wal")
        self.signature = None
        self.rows = {}

    @staticmethod
    def stamp(path):
        try:
            stat = path.stat()
            return stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
        except OSError:
            return None

    def poll(self, keys):
        if not keys:
            self.signature, self.rows = None, {}
            return self.rows
        signature = (frozenset(keys), self.stamp(self.path), self.stamp(self.wal))
        if signature == self.signature:
            return self.rows
        try:
            with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.05)) as db:
                db.execute("BEGIN")  # One read snapshot during concurrent desktop writes.
                rows = {}
                for key in keys:
                    row = db.execute("""
                        SELECT cwd FROM local_thread_catalog
                        WHERE host_id=? AND thread_id=? AND missing_candidate=0
                    """, split_thread_key(key)).fetchone()
                    if row and isinstance(row[0], str):
                        rows[key] = row[0]
        except (OSError, sqlite3.Error):
            # No new conclusions on an unavailable optional index.
            return {key: cwd for key, cwd in self.rows.items() if key in keys}
        self.signature, self.rows = signature, rows
        return rows
