-- Review-only schema for immutable imported research snapshots.
-- Not a production transaction ledger. Locally tested; not cloud-deployed.
-- Run with a migration owner, never the public read role.
BEGIN;
CREATE SCHEMA IF NOT EXISTS pms_private;
CREATE SCHEMA IF NOT EXISTS pms_public;
CREATE TABLE IF NOT EXISTS pms_private.snapshots (
    snapshot_id text PRIMARY KEY CHECK (length(snapshot_id) = 64),
    run_key text UNIQUE NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    CHECK ((payload->'reconciled' = 'true'::jsonb) IS TRUE)
);
CREATE TABLE IF NOT EXISTS pms_public.snapshots (
    snapshot_id text PRIMARY KEY REFERENCES pms_private.snapshots(snapshot_id),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    projection jsonb NOT NULL
);
CREATE OR REPLACE FUNCTION pms_private.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only table'; END $$;
CREATE TRIGGER immutable_private BEFORE UPDATE OR DELETE ON pms_private.snapshots
FOR EACH ROW EXECUTE FUNCTION pms_private.reject_mutation();
CREATE TRIGGER immutable_public BEFORE UPDATE OR DELETE ON pms_public.snapshots
FOR EACH ROW EXECUTE FUNCTION pms_private.reject_mutation();
REVOKE ALL ON SCHEMA pms_private FROM PUBLIC;
REVOKE ALL ON SCHEMA pms_public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA pms_private FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA pms_public FROM PUBLIC;
-- Account roles are to be provisioned privately. Do not embed passwords here.
-- pms_writer: USAGE on both schemas, SELECT/INSERT on both tables, no DDL/update/delete.
-- pms_public_read: USAGE on pms_public, SELECT on pms_public.snapshots only.
-- Writer transaction: advisory lock for run_key, conflict/hash check, private+public
-- inserts atomically, commit. A production journal requires the upstream event contract.
COMMIT;
