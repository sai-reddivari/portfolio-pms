"""PostgreSQL persistence adapter; integration tests require an isolated test DB."""
import hashlib
import json
from .store import canonical
from .public import project


class PostgresStore:
    def __init__(self, dsn):
        import psycopg
        # Use runtime-injected credentials. Never log connection strings or errors.
        self.db = psycopg.connect(dsn, connect_timeout=10)

    def save(self, run_key, payload):
        if payload.get('reconciled') is not True:
            raise ValueError('Unreconciled snapshot rejected')
        encoded = canonical(payload)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        public = canonical(project(digest, payload))
        with self.db.transaction():
            # Serialize this economic run, including concurrent scheduler deliveries.
            self.db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (run_key,))
            previous = self.db.execute('SELECT snapshot_id FROM pms_private.snapshots WHERE run_key=%s',
                                       (run_key,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError('Input changed: explicit correction version required')
                return digest, False
            self.db.execute('INSERT INTO pms_private.snapshots(snapshot_id,run_key,payload) VALUES (%s,%s,%s::jsonb)',
                            (digest, run_key, encoded))
            self.db.execute('INSERT INTO pms_public.snapshots(snapshot_id,projection) VALUES (%s,%s::jsonb)',
                            (digest, public))
        return digest, True

    def read_public(self):
        # A SELECT-only role can execute this; no private-schema access is needed.
        with self.db.transaction():
            # Bound lock waits and query execution so a blocked DB cannot occupy
            # the web request threads indefinitely. Reset automatically at commit.
            self.db.execute("SET LOCAL statement_timeout = '5s'")
            row = self.db.execute('SELECT projection FROM pms_public.snapshots '
                                  'ORDER BY recorded_at DESC, snapshot_id DESC LIMIT 1').fetchone()
        if not row:
            raise LookupError('No committed public snapshot')
        return row[0]

    def close(self):
        self.db.close()
