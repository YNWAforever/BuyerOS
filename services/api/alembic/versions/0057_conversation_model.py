"""Conversation-only API receipt transitions; preserve liability on rollback.

No seeded approvals, provider selection, budgets or execution work. Conversation
uses the existing model_receipts table and a terminal, never queued outbox fence.
"""
from alembic import op
import sqlalchemy as sa

revision = '0057_conversation_model'
down_revision = '0056_policy_activation'
branch_labels = depends_on = None


def _fences(head):
    for service in ('search', 'model', 'contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.execute("ALTER FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) RENAME TO buyeros_receipt_dependency_expired_0056")
    op.execute("""
    CREATE FUNCTION public.buyeros_receipt_dependency_expired(ws uuid, service_name text, receipt uuid, payload jsonb)
    RETURNS boolean LANGUAGE sql STABLE SET search_path=pg_catalog,public AS $dependency$
      SELECT public.buyeros_receipt_dependency_expired_0056(ws,service_name,receipt,payload)
      OR (ws=NULLIF(current_setting('app.workspace_id',true),'')::uuid AND service_name='model'
          AND payload#>>'{basis,schema}'='conversation-basis.v1' AND (
            NOT EXISTS(SELECT 1 FROM public.projects p JOIN public.icp_versions i ON i.workspace_id=p.workspace_id AND i.id=p.active_icp_version_id
              WHERE p.workspace_id=ws AND p.id::text=payload#>>'{basis,project_id}' AND p.status='active'
              AND i.id::text=payload#>>'{basis,icp_version_id}' AND i.approved_at IS NOT NULL AND i.approved_by IS NOT NULL
              AND i.superseded_at IS NULL AND i.content_hash=payload#>>'{basis,icp_hash}'
              AND p.offer_revision::text=payload#>>'{basis,offer_revision}')
            OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(COALESCE(payload#>'{basis,document_ids}','[]'::jsonb)) d(id)
              WHERE NOT EXISTS(SELECT 1 FROM public.offer_documents o WHERE o.workspace_id=ws AND o.id::text=d.id
                AND o.project_id::text=payload#>>'{basis,project_id}' AND o.status='ready' AND o.deleted_at IS NULL AND o.retention_until>now()))))
    $dependency$;
    REVOKE ALL ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) TO buyeros_api,buyeros_worker;

    CREATE FUNCTION public.buyeros_transition_conversation_receipt(receipt uuid, next_state text, body jsonb, digest text)
    RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $transition$
    DECLARE r public.model_receipts; op_status text;
    BEGIN
      IF public.buyeros_model_receipts_writable() IS NOT TRUE THEN RETURN false; END IF;
      SELECT * INTO r FROM public.model_receipts WHERE id=receipt
        AND workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid
        AND request#>>'{basis,schema}'='conversation-basis.v1' AND intent_key LIKE 'conversation:%'
        AND redacted_at IS NULL;
      IF NOT FOUND THEN RETURN false; END IF;
      SELECT status INTO op_status FROM public.provider_operations WHERE workspace_id=r.workspace_id AND id=r.operation_id FOR UPDATE;
      SELECT * INTO r FROM public.model_receipts WHERE id=receipt AND workspace_id=r.workspace_id AND redacted_at IS NULL FOR UPDATE;
      IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM public.outbox_events e JOIN public.worker_runtime_control c ON c.singleton=1
          WHERE e.workspace_id=r.workspace_id AND e.id=r.outbox_id AND e.event_type='conversation.model' AND e.state='done'
          AND e.intent_key=r.intent_key AND e.fencing_generation=r.generation AND e.runtime_backend=r.runtime_backend
          AND e.runtime_epoch=r.runtime_epoch AND c.backend=r.runtime_backend AND c.epoch=r.runtime_epoch)
        THEN RETURN false; END IF;
      IF next_state='submitting' THEN
        IF r.state<>'prepared' OR op_status<>'reserved' OR body IS NOT NULL OR digest IS NOT NULL
          OR r.retention_until<=now() OR public.buyeros_receipt_dependency_expired(r.workspace_id,'model',r.id,r.request)
          OR NOT EXISTS(SELECT 1 FROM public.budget_reservations b WHERE b.workspace_id=r.workspace_id AND b.operation_id=r.operation_id
            AND b.state='active' AND b.currency='USD' AND b.price_version=r.pricing_version
            AND b.upper_bound=0.100000 AND b.remaining_hold=b.upper_bound)
          OR NOT EXISTS(SELECT 1 FROM public.provider_operations p WHERE p.id=r.operation_id AND p.workspace_id=r.workspace_id
            AND p.intent_key=r.intent_key AND p.capability='model' AND NOT p.cancel_requested AND p.deadline>now())
          THEN RETURN false; END IF;
      ELSIF next_state IN ('received','unknown') THEN
        IF r.state<>'submitting' OR op_status<>'submitting' THEN RETURN false; END IF;
        IF next_state='unknown' AND (body IS NOT NULL OR digest IS NOT NULL) THEN RETURN false; END IF;
        IF next_state='received' AND (body IS NULL OR digest IS NULL OR jsonb_typeof(body)<>'object'
          OR octet_length(body::text)>262144 OR digest !~ '^[a-f0-9]{64}$') THEN RETURN false; END IF;
      ELSE RETURN false;
      END IF;
      UPDATE public.model_receipts SET state=next_state,response=body,response_hash=digest,updated_at=now() WHERE id=r.id;
      UPDATE public.provider_operations SET status=CASE WHEN next_state='received' THEN 'accepted' ELSE next_state END,
        updated_at=now() WHERE workspace_id=r.workspace_id AND id=r.operation_id;
      -- Never settle or release a hold from model usage or an uncertain result.
      RETURN true;
    END $transition$;
    REVOKE ALL ON FUNCTION public.buyeros_transition_conversation_receipt(uuid,text,jsonb,text) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_transition_conversation_receipt(uuid,text,jsonb,text) TO buyeros_api;
    """)
    _fences(revision)


def downgrade():
    # A financial receipt is not disposable migration metadata.
    op.execute('ALTER TABLE public.model_receipts NO FORCE ROW LEVEL SECURITY')
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM public.model_receipts WHERE request#>>'{basis,schema}'='conversation-basis.v1' OR intent_key LIKE 'conversation:%')")).scalar_one():
        raise RuntimeError('0057 downgrade blocked: preserve conversation receipts and liability')
    op.execute('ALTER TABLE public.model_receipts FORCE ROW LEVEL SECURITY')
    op.execute('DROP FUNCTION public.buyeros_transition_conversation_receipt(uuid,text,jsonb,text)')
    op.execute('DROP FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb)')
    op.execute('ALTER FUNCTION public.buyeros_receipt_dependency_expired_0056(uuid,text,uuid,jsonb) RENAME TO buyeros_receipt_dependency_expired')
    _fences(down_revision)
