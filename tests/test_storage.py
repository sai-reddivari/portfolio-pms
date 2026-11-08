import concurrent.futures
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from paper_pms.store import Store


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'pms.db'
        self.store = Store(self.path)
        self.payload = {'reconciled': True, 'value': 1}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_duplicate_and_changed_inputs(self):
        first = self.store.save('cycle', self.payload)
        self.assertEqual(self.store.save('cycle', self.payload), (first[0], False))
        with self.assertRaises(ValueError):
            self.store.save('cycle', {'reconciled': True, 'value': 2})
        self.assertEqual(self.store.load()[1], self.payload)

    def test_rollback_and_retry(self):
        with self.assertRaises(RuntimeError):
            self.store.save('cycle', self.payload, fail_before_commit=True)
        with self.assertRaises(LookupError):
            self.store.load()
        self.assertTrue(self.store.save('cycle', self.payload)[1])

    def test_mutation_rejected(self):
        self.store.save('cycle', self.payload)
        for sql in ['DELETE FROM snapshots', "UPDATE snapshots SET payload='{}'"]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute(sql)
        self.store.db.rollback()

    def test_restore(self):
        self.store.save('cycle', self.payload)
        backup = Path(self.temp.name) / 'backup.db'
        self.store.backup(backup)
        restored = Store(backup)
        self.assertEqual(restored.load(), self.store.load())
        restored.close()

    def test_concurrent_delivery(self):
        def attempt(_):
            s = Store(self.path)
            try:
                return s.save('cycle', self.payload)[1]
            finally:
                s.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_unreconciled_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save('cycle', {'reconciled': False})


if __name__ == '__main__':
    unittest.main()
