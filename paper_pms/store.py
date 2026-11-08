"""Append-only local snapshot persistence. SQLite is a test backend only."""
import hashlib
import json
from pathlib import Path
import sqlite3


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY, run_key TEXT UNIQUE NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            payload TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON snapshots
            BEGIN SELECT RAISE(ABORT, 'append-only'); END;
          CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON snapshots
            BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        ''')

    def save(self, run_key, payload, fail_before_commit=False):
        if payload.get('reconciled') is not True:
            raise ValueError('Unreconciled snapshot rejected')
        encoded = canonical(payload)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT id FROM snapshots WHERE run_key=?', (run_key,)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError('Input changed: use explicit correction version')
                return digest, False
            self.db.execute('INSERT INTO snapshots(id,run_key,payload) VALUES (?,?,?)',
                            (digest, run_key, encoded))
            if fail_before_commit:
                raise RuntimeError('Injected crash before commit')
        return digest, True

    def load(self, snapshot_id=None):
        if snapshot_id:
            row = self.db.execute('SELECT id,payload FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
        else:
            row = self.db.execute('SELECT id,payload FROM snapshots ORDER BY rowid DESC LIMIT 1').fetchone()
        if not row:
            raise LookupError('No committed snapshot')
        if hashlib.sha256(row[1].encode()).hexdigest() != row[0]:
            raise ValueError('Snapshot integrity failure')
        return row[0], json.loads(row[1])

    def backup(self, path):
        if Path(path).exists():
            raise FileExistsError('Backup destination already exists')
        destination = sqlite3.connect(path)
        try:
            self.db.backup(destination)
        finally:
            destination.close()

    def close(self):
        self.db.close()
