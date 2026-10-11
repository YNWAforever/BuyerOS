BEGIN;

-- Running upgrade 0037_bulk_manifests -> 0038_c61_workspace_directory

DO $owner_check$
    BEGIN
        IF current_user IN ('buyeros_api','buyeros_worker') OR NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=current_user
                AND (rolsuper OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'directory requires an existing privileged migration owner'
                USING ERRCODE='42501';
        END IF;
    END $owner_check$;;

CREATE INDEX ix_memberships_active_user_workspace ON public.memberships (user_id, workspace_id) WHERE active IS TRUE;

CREATE FUNCTION public.buyeros_workspace_directory(p_actor uuid, p_offset bigint, p_limit integer)
    RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $directory$
    DECLARE result jsonb;
    BEGIN
        IF session_user <> 'buyeros_api' OR p_actor IS NULL
            OR current_setting('app.user_id', true) IS DISTINCT FROM p_actor::text THEN
            RAISE EXCEPTION 'trusted canonical actor binding required' USING ERRCODE='42501';
        END IF;
        IF current_setting('transaction_read_only') <> 'on' THEN
            RAISE EXCEPTION 'directory requires a read-only transaction' USING ERRCODE='25006';
        END IF;
        IF p_offset IS NULL OR p_offset < 0 OR p_limit IS NULL OR p_limit < 1 OR p_limit > 100 THEN
            RAISE EXCEPTION 'bounded pagination required' USING ERRCODE='22023';
        END IF;
        WITH visible AS MATERIALIZED (
            SELECT w.id, w.name, m.id AS membership_id, m.roles
            FROM public.memberships AS m JOIN public.workspaces AS w ON w.id=m.workspace_id
            WHERE m.user_id=p_actor AND m.active IS TRUE
        ), page AS (
            SELECT * FROM visible ORDER BY id OFFSET p_offset LIMIT p_limit
        )
        SELECT jsonb_build_object(
            'items', COALESCE((SELECT jsonb_agg(jsonb_build_object(
                'id',id::text,'name',name,'membership_id',membership_id::text,
                'roles',to_jsonb(roles),'data_mode','live') ORDER BY id) FROM page),'[]'::jsonb),
            'offset',p_offset,'limit',p_limit,'total',(SELECT count(*) FROM visible)
        ) INTO result;
        RETURN result;
    END $directory$;;

REVOKE ALL ON FUNCTION public.buyeros_workspace_directory(uuid,bigint,integer) FROM PUBLIC, buyeros_worker;

GRANT EXECUTE ON FUNCTION public.buyeros_workspace_directory(uuid,bigint,integer) TO buyeros_api;

UPDATE alembic_version SET version_num='0038_c61_workspace_directory' WHERE alembic_version.version_num = '0037_bulk_manifests';

COMMIT;

