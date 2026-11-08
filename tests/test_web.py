import unittest
from paper_pms.web import create_app


class WebTests(unittest.TestCase):
    def request(self, path, method='GET', reader=lambda: {'mode': 'synthetic-replay'}):
        result = {}
        def start(status, headers):
            result.update(status=status, headers=dict(headers))
        result['body'] = b''.join(create_app(reader)({'PATH_INFO': path, 'REQUEST_METHOD': method}, start))
        return result

    def test_write_and_unknown_routes(self):
        self.assertTrue(self.request('/', 'POST')['status'].startswith('405'))
        self.assertTrue(self.request('/../research.lock.json')['status'].startswith('404'))

    def test_synthetic_never_fresh(self):
        response = self.request('/health/freshness')
        self.assertTrue(response['status'].startswith('503'))
        self.assertIn(b'"fresh":false', response['body'])

    def test_error_is_sanitized(self):
        def broken():
            raise RuntimeError('postgres://private-password@example.invalid/db')
        response = self.request('/snapshot.json', reader=broken)
        self.assertTrue(response['status'].startswith('503'))
        self.assertNotIn(b'password', response['body'])

    def test_liveness_has_no_db_dependency_and_head_is_empty(self):
        def broken():
            raise RuntimeError('unavailable')
        self.assertTrue(self.request('/health/live', reader=broken)['status'].startswith('200'))
        self.assertEqual(self.request('/health/live', 'HEAD')['body'], b'')


if __name__ == '__main__':
    unittest.main()
