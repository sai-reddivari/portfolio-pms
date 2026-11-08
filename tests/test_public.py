import unittest
from paper_pms.public import project, render


class PublicTests(unittest.TestCase):
    def test_allowlist_and_escaping(self):
        payload = {'mode': 'synthetic-replay', 'session_dates': ['2026-11-10'],
                   'research_commit': 'abc', 'limitations': ['<script>bad()</script>'],
                   'private_secret': 'must-not-appear', 'accounts': []}
        public = project('snapshot', payload)
        self.assertNotIn('private_secret', public)
        page = render(public)
        self.assertNotIn('<script>', page)
        self.assertNotIn('must-not-appear', page)
        self.assertIn('NOT LIVE', page)


if __name__ == '__main__':
    unittest.main()
