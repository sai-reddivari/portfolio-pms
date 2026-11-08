"""Real-engine acceptance tests. Always create a private, disposable local cluster.

PMS_TEST_PG_BIN must point to a directory with initdb, pg_ctl, pg_dump, pg_restore.
No existing database/DSN is accepted. Run with a Python environment with psycopg.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import psycopg
from psycopg import sql
from paper_pms.postgres import PostgresStore
from paper_pms.public import project
from paper_pms.web import create_app

ROOT = Path(__file__).resolve().parents[1]


class PostgresAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin = Path(os.environ['PMS_TEST_PG_BIN']).resolve()
        cls.temp = tempfile.TemporaryDirectory(prefix='pms-pg-', dir='/private/tmp')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.data = cls.root / 'data'
        cls.run_tool('initdb', '-D', str(cls.data), '-U', 'pms_test_admin',
                     '--auth-local=trust', '--auth-host=reject', '--no-locale', '-E', 'UTF8')
        # Unix socket in a 0700 temp directory, no TCP listening, no global service.
        cls.run_tool('pg_ctl', '-D', str(cls.data), '-l', str(cls.root/'server.log'),
                     '-o', f"-c listen_addresses='' -c unix_socket_directories='{cls.root}'", '-w', 'start')
        cls.addClassCleanup(cls.run_tool, 'pg_ctl', '-D', str(cls.data), '-m', 'immediate', '-w', 'stop')
        cls.base = f'host={cls.root} user=pms_test_admin dbname=postgres'
        with psycopg.connect(cls.base, autocommit=True) as db:
            db.execute('CREATE ROLE pms_writer LOGIN')
            db.execute('CREATE ROLE pms_public_read LOGIN')
        cls.payload = {'reconciled': True, 'mode': 'synthetic-replay',
                       'session_dates': ['2026-11-10'], 'research_commit': 'test-fixture',
                       'limitations': ['synthetic integration test'], 'accounts': [],
                       'private_secret': 'never-public'}

    @classmethod
    def run_tool(cls, name, *args):
        result = subprocess.run([str(cls.bin/name), *args], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'{name} failed: {result.stderr}')
        return result.stdout

    def setUp(self):
        self.dbname = self._testMethodName
        with psycopg.connect(self.base, autocommit=True) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.dbname)))
        self.owner = f'host={self.root} user=pms_test_admin dbname={self.dbname}'
        with psycopg.connect(self.owner, autocommit=True) as db:
            db.execute((ROOT/'deploy/postgres-schema-proposal.sql').read_text())
            db.execute((ROOT/'deploy/database-roles.review.sql').read_text())
        self.writer = PostgresStore(f'host={self.root} user=pms_writer dbname={self.dbname}')
        self.reader = PostgresStore(f'host={self.root} user=pms_public_read dbname={self.dbname}')
        self.addCleanup(self.writer.close)
        self.addCleanup(self.reader.close)

    def test_duplicate_and_changed_input(self):
        digest, inserted = self.writer.save('cycle', self.payload)
        self.assertTrue(inserted)
        self.assertEqual(self.writer.save('cycle', self.payload), (digest, False))
        changed = dict(self.payload, limitations=['changed'])
        with self.assertRaises(ValueError):
            self.writer.save('cycle', changed)
        self.assertEqual(self.reader.read_public(), project(digest, self.payload))

    def test_concurrent_delivery(self):
        def attempt(_):
            store = PostgresStore(f'host={self.root} user=pms_writer dbname={self.dbname}')
            try:
                return store.save('cycle', self.payload)[1]
            finally:
                store.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_public_insert_failure_rolls_back_private_insert(self):
        with psycopg.connect(self.owner, autocommit=True) as db:
            db.execute('REVOKE INSERT ON pms_public.snapshots FROM pms_writer')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.writer.save('cycle', self.payload)
        with psycopg.connect(self.owner, autocommit=True) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM pms_private.snapshots').fetchone()[0], 0)
            db.execute('GRANT INSERT ON pms_public.snapshots TO pms_writer')
        self.assertTrue(self.writer.save('cycle', self.payload)[1])

    def test_public_role_cannot_read_private_or_write(self):
        self.writer.save('cycle', self.payload)
        for query in ['SELECT * FROM pms_private.snapshots', 'DELETE FROM pms_public.snapshots',
                      "UPDATE pms_public.snapshots SET projection='{}'", 'TRUNCATE pms_public.snapshots']:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.reader.db.transaction():
                    self.reader.db.execute(query)
        self.assertNotIn('private_secret', self.reader.read_public())

    def test_append_only_triggers_and_reconciliation_constraint(self):
        self.writer.save('cycle', self.payload)
        with psycopg.connect(self.owner, autocommit=True) as db:
            for table in ['pms_private.snapshots', 'pms_public.snapshots']:
                for operation in ['DELETE FROM ', 'UPDATE ']:
                    query = operation + table
                    if operation.startswith('UPDATE'):
                        query += ' SET recorded_at=now()'
                    with self.assertRaises(psycopg.errors.RaiseException):
                        db.execute(query)
            for payload in [{}, {'reconciled': False}, {'reconciled': 'true'}]:
                with self.assertRaises(psycopg.errors.CheckViolation):
                    db.execute('INSERT INTO pms_private.snapshots VALUES (%s,%s,now(),%s::jsonb)',
                               ('f'*64, 'bad', json.dumps(payload)))

    def test_backup_restore(self):
        self.writer.save('cycle', self.payload)
        backup = self.root / 'snapshot.dump'
        self.run_tool('pg_dump', '-d', self.owner, '-Fc', '-f', str(backup))
        with psycopg.connect(self.base, autocommit=True) as db:
            db.execute('CREATE DATABASE pms_restored')
        restore_dsn = f'host={self.root} user=pms_test_admin dbname=pms_restored'
        self.run_tool('pg_restore', '-d', restore_dsn, '--exit-on-error', str(backup))
        restored = PostgresStore(f'host={self.root} user=pms_public_read dbname=pms_restored')
        try:
            self.assertEqual(restored.read_public(), self.reader.read_public())
        finally:
            restored.close()
        with psycopg.connect(restore_dsn) as db:
            self.assertEqual(db.execute('SELECT payload FROM pms_private.snapshots').fetchone()[0], self.payload)

    def test_wsgi_reads_committed_projection(self):
        self.writer.save('cycle', self.payload)
        for path in ['/', '/snapshot.json', '/health/freshness']:
            result = {}
            body = b''.join(create_app(self.reader.read_public)(
                {'REQUEST_METHOD': 'GET', 'PATH_INFO': path},
                lambda status, headers: result.update(status=status)))
            self.assertTrue(result['status'].startswith('503' if 'freshness' in path else '200'))
            self.assertNotIn(b'never-public', body)
        self.assertIn('NOT LIVE', self.reader.read_public()['status'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
