-- REVIEW ONLY. Run as migration owner after the schema is applied and these
-- dedicated, non-owner, non-superuser login roles have been privately created.
-- No credentials are stored in source. Never grant role membership to the web role.
BEGIN;
GRANT USAGE ON SCHEMA pms_private, pms_public TO pms_writer;
GRANT SELECT, INSERT ON pms_private.snapshots, pms_public.snapshots TO pms_writer;
GRANT USAGE ON SCHEMA pms_public TO pms_public_read;
GRANT SELECT ON pms_public.snapshots TO pms_public_read;
COMMIT;
