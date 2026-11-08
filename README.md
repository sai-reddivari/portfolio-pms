# Portfolio PMS — synthetic integration

A local paper-portfolio integration that calls a pinned research replay, persists reconciled snapshots, and renders a read-only dashboard. This is a development fixture, not an operating fund, live trading system, or deployed PMS.

## What is implemented

- Ten synthetic names: seven long and three short, over four fixture sessions spanning a weekend.
- An unhedged control and a demonstration model put share the same core portfolio.
- Independent gross/concentration limits and NAV reconciliation checks.
- Immutable SQLite snapshots for local replay, and a PostgreSQL adapter with atomic private/public writes and idempotent delivery.
- An allowlisted public projection and read-only WSGI dashboard. Synthetic data never passes the market-freshness endpoint.

The separate research project owns ledger mathematics. This repository contains only its commit/file-hash manifest and a caller adapter, not its source. `research.lock.json` pins commit `c36518a8e4aa6b533e19e0346b21d3df863a3823`; the adapter refuses a source tree that differs from that manifest. Availability of that revision as a remotely installable release remains unverified.

## Local preview and tests

Open `preview/index.html` to inspect the synthetic fixture without installing the research dependency. `preview/snapshot.json` is the allowlisted public projection. Future-dated fixture observations are synthetic, not observed market prices.

Run the unit suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

To replay the fixture, supply a separately obtained, matching research source tree and an environment with its dependencies installed:

```sh
python -m paper_pms \
  --research-source /absolute/path/to/verified-research-source \
  --database work/pms-fixture.db \
  --output preview
```

Create `work/` first. The verified replay environment used pandas 3.1.1, numpy 2.5.4, and scipy 1.18.1; a portable research dependency lock remains a release gate. The initial snapshot SHA-256 is `ce8c0b87e9b8bf5e5dae45995cd36cce324827688ce80ad0f8fae3d1db2430b7`. Repeating the same run returns `inserted:false`.

Install `requirements-runtime.txt` in an isolated environment for the web/PostgreSQL adapter. Set `PMS_PUBLIC_DATABASE_URL` privately to a SELECT-only role, then run:

```sh
gunicorn --no-control-socket --bind 127.0.0.1:8080 paper_pms.web:application
```

`/health/live` checks process availability. `/health/freshness` returns 503 for this synthetic-only implementation. Database errors are sanitized. There are no public write routes or automatic migrations.

## Validation

Eleven unit tests and eight isolated PostgreSQL 18.6 acceptance tests passed. Coverage includes duplicate/concurrent delivery, changed-input rejection, transaction rollback/retry, append-only rules, strict boolean reconciliation, role restrictions, logical backup/restore, public projection, and WSGI reads. See `integration/README.md` for the disposable database harness. The PostgreSQL tests found and fixed a constraint that accepted the string `"true"` instead of JSON boolean `true`.

The Linux amd64 web container also passed [GitHub Actions acceptance](https://github.com/sai-reddivari/portfolio-pms/actions/runs/42432304738): digest-pinned base image, non-root user, read-only filesystem, PostgreSQL-backed HTML/JSON, write rejection, and sanitized database-outage responses. Public database reads have a five-second statement timeout; a real lock-wait test confirms rollback and recovery. The image is web-only; it does not package the research worker dependency.

These checks do not certify managed-cloud network/TLS behavior or a prospective trading ledger. A separate disposable DigitalOcean static-site smoke test passed deployment, unattended redeployment, HTTP health, and cleanup; that test did not deploy this PMS application.

## Release gates and deployment review

`deploy/app-spec.review.yaml`, `deploy/resources-review.json`, and the database schema/role scripts are review material, not authorization to provision resources. Automatic deployment and scheduled execution are disabled. Runtime secrets must be injected privately and never committed.

Remaining gates:

- A reviewed, installable upstream interface for incremental dated events, calendar accrual, valuation, and reconciliation.
- Scheduler retry/backfill behavior, archive recovery, and managed-cloud network/TLS validation.
- Repository-specific cloud source authorization and concrete resource review before persistent deployment.

The fixture uses zero financing rate because upstream financing is session-based. It does not establish calendar-accrual correctness. All option marks are European model values; fills are simulated. The demonstration put is not a promoted research policy. There are no broker, LLM, or market-data API calls, corporate-action processing, or licensed datasets in this repository.

Build an allowlisted local review archive with `python3 scripts/build_review_package.py`. Generated archives, machine-local evidence, credentials, database files, and the separate research source are excluded from Git.
