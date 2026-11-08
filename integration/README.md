# PostgreSQL acceptance

Run `PMS_TEST_PG_BIN=/absolute/path/to/postgres/bin python -m unittest discover -s integration -v` using an environment with `requirements-runtime.txt` installed. The harness starts its own disposable cluster, creates fixture databases and roles, then shuts down and removes the cluster even on test failure. It never accepts an existing database connection string. It uses a Unix socket inside a private temporary directory and disables TCP connections. Local trust authentication is confined to that directory; it is not a cloud authentication configuration.

The suite tests duplicate and conflicting delivery, concurrent writes, transaction rollback when the public insert fails, the public role's private-read/write restrictions, append-only triggers, strict reconciliation, logical backup/restore, and WSGI reads from committed projections. These tests validate snapshot persistence, not a prospective trading ledger or managed-cloud network/TLS behavior.

The review SQL grants only schema usage, SELECT, and the writer's INSERT. Create dedicated non-owner/non-superuser roles privately before applying it in a reviewed environment. A database owner can override triggers and permissions; immutable snapshots are an application invariant, not tamper-proof storage against administrators.
