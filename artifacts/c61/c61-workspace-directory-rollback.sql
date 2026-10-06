BEGIN;

-- Running downgrade 0038_c61_workspace_directory -> 0037_bulk_manifests

DROP FUNCTION public.buyeros_workspace_directory(uuid,bigint,integer);

DROP INDEX public.ix_memberships_active_user_workspace;

UPDATE alembic_version SET version_num='0037_bulk_manifests' WHERE alembic_version.version_num = '0038_c61_workspace_directory';

COMMIT;

