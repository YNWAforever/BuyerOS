"""Monotonic invalidation and bounded physical erasure, separate from money.

Dependencies remain content-free so subsequent pages and descendants can still
be found. No rendered export blob or cross-request content cache is introduced.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import select, text
from ..api.errors import ApiError
from ..db.sales_tasks import SalesTask
from ..sales.contracts import PurgeReceipt


# Reuse explicit project policy history. No invented global duration: authored
# notes with no applicable decision retain the existing discussion lifecycle.
# Source deadlines/revocations are independently checked and always win.
POLICY_DUE = '''WITH latest AS (
  SELECT DISTINCT ON(project_id,purpose) project_id,purpose,retention_days FROM
    (SELECT subject_id project_id,purpose,retention_days,version,created_at,id
     FROM policy_decisions WHERE workspace_id=:ws AND subject_type='project') p
  ORDER BY project_id,purpose,version DESC,created_at DESC,id DESC
) SELECT t.id,t.project_id FROM sales_tasks t JOIN latest p ON p.project_id=t.project_id
  WHERE t.workspace_id=:ws AND t.created_at+make_interval(days=>p.retention_days)<=now()
  AND NOT EXISTS(SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws
    AND x.target_id=t.id AND x.kind='task' AND x.completed_at IS NOT NULL)'''


async def tombstone(session, workspace_id, project_id, target_id, kind):
    await session.execute(text('''INSERT INTO sales_content_tombstones
      (id,workspace_id,project_id,target_id,kind) VALUES(:id,:ws,:project,:target,:kind)
      ON CONFLICT(workspace_id,target_id,kind) DO NOTHING'''),
      dict(id=uuid4(), ws=workspace_id, project=project_id, target=target_id, kind=kind))


async def require_current(session, workspace_id, target_ids):
    if not target_ids:
        return
    row = await session.scalar(text('''SELECT EXISTS(SELECT 1 FROM sales_content_tombstones
      WHERE workspace_id=:ws AND target_id=ANY(:ids))'''),
      dict(ws=workspace_id, ids=list(target_ids)))
    if row:
        raise ApiError(404, 'SOURCE_UNAVAILABLE', 'content is no longer available')
    due=await session.scalar(text('SELECT EXISTS(SELECT 1 FROM ('+POLICY_DUE+''') due
      WHERE due.id=ANY(:ids) OR due.id IN(SELECT task_id FROM sales_outputs
        WHERE workspace_id=:ws AND id=ANY(:ids)))'''),dict(ws=workspace_id,ids=list(target_ids)))
    if due:
        raise ApiError(404,'SOURCE_UNAVAILABLE','content retention has elapsed')


# UNION deduplicates cycles. The result is processed in pages of at most 50
# tasks; root tombstones reject new reads and dispatch before the first page.
CLOSURE = '''WITH RECURSIVE affected(id) AS (
  SELECT CAST(:target AS uuid)
  UNION
  SELECT edge.destination FROM affected a JOIN (
    SELECT source_id origin,task_id destination FROM sales_task_dependencies WHERE workspace_id=:ws
    UNION SELECT source_id,output_id FROM sales_output_dependencies WHERE workspace_id=:ws
    UNION SELECT native_id,output_id FROM sales_output_native_links WHERE workspace_id=:ws
    UNION SELECT task_id,id FROM sales_outputs WHERE workspace_id=:ws
    UNION SELECT id,task_id FROM sales_outputs WHERE workspace_id=:ws
    UNION SELECT e.source_document_id,b.id FROM evidence e JOIN project_buyers b
      ON b.workspace_id=e.workspace_id AND b.company_id=e.company_id AND b.project_id=e.project_id WHERE e.workspace_id=:ws
    UNION SELECT source_document_id,run_id FROM evidence WHERE workspace_id=:ws AND run_id IS NOT NULL
    UNION SELECT o.id,d.source_id FROM offer_documents o JOIN sales_task_dependencies d
      ON d.workspace_id=o.workspace_id AND d.project_id=o.project_id AND d.kind IN ('profile','project_fact') WHERE o.workspace_id=:ws
    UNION SELECT c.id,b.id FROM contact_points c JOIN project_buyers b ON b.workspace_id=c.workspace_id AND b.company_id=c.company_id WHERE c.workspace_id=:ws
    UNION SELECT q.buyer_id,r.id FROM xverum_quotes q JOIN xverum_credit_reservations z ON z.quote_id=q.id AND z.workspace_id=q.workspace_id
      JOIN xverum_receipts r ON r.reservation_id=z.id AND r.workspace_id=q.workspace_id WHERE q.workspace_id=:ws
    UNION SELECT q.connection_id,r.id FROM xverum_quotes q JOIN xverum_credit_reservations z ON z.quote_id=q.id AND z.workspace_id=q.workspace_id
      JOIN xverum_receipts r ON r.reservation_id=z.id AND r.workspace_id=q.workspace_id WHERE q.workspace_id=:ws
    UNION SELECT q.source_receipt_id,r.id FROM xverum_quotes q JOIN xverum_credit_reservations z ON z.quote_id=q.id AND z.workspace_id=q.workspace_id
      JOIN xverum_receipts r ON r.reservation_id=z.id AND r.workspace_id=q.workspace_id WHERE q.workspace_id=:ws AND q.source_receipt_id IS NOT NULL
    UNION SELECT source_id,enrichment_id FROM xverum_enrichment_dependencies WHERE workspace_id=:ws
    UNION SELECT task_id,id FROM xverum_enrichments WHERE workspace_id=:ws AND task_id IS NOT NULL
    UNION SELECT id,task_id FROM xverum_enrichments WHERE workspace_id=:ws AND task_id IS NOT NULL
    UNION SELECT stage_id,id FROM xverum_tool_receipts WHERE workspace_id=:ws
    UNION SELECT id,stage_id FROM xverum_tool_receipts WHERE workspace_id=:ws
    UNION SELECT task_id,id FROM xverum_stages WHERE workspace_id=:ws AND task_id IS NOT NULL
    UNION SELECT id,task_id FROM xverum_stages WHERE workspace_id=:ws AND task_id IS NOT NULL
  ) edge ON edge.origin=a.id
) '''


async def purge_page(session, workspace_id, project_id, target_id):
    from ..execution.sales_tasks import lock_authority
    from ..db.conversation_threads import ConversationThread
    await lock_authority(session, workspace_id)
    # Provider projections are mutable by the existing owner, including standalone
    # search parents. Do not erase credits, request identities or settlement links.
    tool_ids=list((await session.scalars(text(CLOSURE+'''SELECT t.id FROM xverum_stages t
      JOIN affected a ON a.id=t.id WHERE t.workspace_id=:ws
      AND NOT EXISTS(SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws
        AND x.target_id=t.id AND x.kind='provider' AND x.completed_at IS NOT NULL)
      ORDER BY t.id LIMIT 50'''),dict(ws=workspace_id,target=target_id))).all())
    for tool_id in tool_ids:
        await tombstone(session,workspace_id,project_id,tool_id,'provider')
        await session.execute(text('SELECT public.buyeros_purge_xverum_stage(:stage)'),dict(stage=tool_id))
    enrichment_ids=list((await session.scalars(text(CLOSURE+'''SELECT e.id FROM xverum_enrichments e
      JOIN affected a ON a.id=e.id WHERE e.workspace_id=:ws
      AND NOT EXISTS(SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws
        AND x.target_id=e.id AND x.kind='enrichment' AND x.completed_at IS NOT NULL)
      ORDER BY e.id LIMIT 50'''),dict(ws=workspace_id,target=target_id))).all())
    for enrichment_id in enrichment_ids:
        await tombstone(session,workspace_id,project_id,enrichment_id,'enrichment')
        await session.execute(text('SELECT public.buyeros_purge_xverum_enrichment(:id)'),dict(id=enrichment_id))
    ids = list((await session.scalars(text(CLOSURE+'''SELECT t.id FROM sales_tasks t
      JOIN affected a ON a.id=t.id WHERE t.workspace_id=:ws
      AND NOT EXISTS(SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws
        AND x.target_id=t.id AND x.kind='task' AND x.completed_at IS NOT NULL)
      ORDER BY t.thread_id,t.id LIMIT 50'''),dict(ws=workspace_id, project=project_id, target=target_id))).all())
    for task_id in ids:
        task = await session.scalar(select(SalesTask).where(SalesTask.workspace_id==workspace_id, SalesTask.id==task_id))
        await session.execute(select(ConversationThread.id).where(ConversationThread.workspace_id==workspace_id,
            ConversationThread.id==task.thread_id).with_for_update())
        await session.execute(select(SalesTask.id).where(SalesTask.workspace_id==workspace_id,
            SalesTask.id==task_id).with_for_update())
        await tombstone(session, workspace_id, task.project_id, task_id, 'task')
        outputs = list((await session.scalars(text('SELECT id FROM sales_outputs WHERE workspace_id=:ws AND task_id=:task'),
            dict(ws=workspace_id,task=task_id))).all())
        for output_id in outputs:
            await tombstone(session, workspace_id, task.project_id, output_id, 'output')
        await session.execute(text('SELECT public.buyeros_purge_sales_task(:task)'), dict(task=task_id))
    return tuple([*ids,*enrichment_ids])


async def invalidate_source(session, scope, source_id: str, reason: str) -> int:
    from ..sales.context import require_scope
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session, scope.workspace_id)
    await require_scope(session, scope)
    if reason not in {'source_deleted','retention_expired','permission_revoked'}:
        raise ValueError('content-free lifecycle reason required')
    source_id=UUID(source_id)
    await tombstone(session, scope.workspace_id, scope.project_id, source_id, 'source')
    return len(await purge_page(session, scope.workspace_id, scope.project_id, source_id))


async def purge_sales_content(session, scope, target_id: UUID) -> PurgeReceipt:
    from ..sales.context import require_scope
    from .conversation_access import load
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session, scope.workspace_id)
    await require_scope(session,scope)
    # A repeat purge may read its tombstone but still requires the current owner.
    row=await session.scalar(select(SalesTask).where(SalesTask.workspace_id==scope.workspace_id,
        SalesTask.project_id==scope.project_id,SalesTask.id==target_id))
    if row is None:
        raise ApiError(404,'NOT_FOUND','purge target unavailable')
    await load(session,scope.workspace_id,scope.project_id,row.thread_id,scope.actor_id,owner=True,lock=True)
    await tombstone(session,scope.workspace_id,scope.project_id,target_id,'task')
    await tombstone(session,scope.workspace_id,scope.project_id,target_id,'source')
    ids=await purge_page(session,scope.workspace_id,scope.project_id,target_id)
    return PurgeReceipt(affected_ids=ids,completed_at=datetime.now(timezone.utc))


async def drain_pending(session, workspace_id):
    """Existing tenant retention sweep continuation: at most one 50-task page."""
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session,workspace_id)
    # Standalone stages have retained-content deadlines even without a task or
    # disconnect. Queue bounded roots from the actual tool deadline; closure
    # erasure also reaches descendant stages while leaving money untouched.
    expired=(await session.execute(text('''SELECT t.stage_id,s.project_id
      FROM xverum_tool_receipts t JOIN xverum_stages s
        ON s.workspace_id=t.workspace_id AND s.id=t.stage_id
      WHERE t.workspace_id=:ws AND t.expires_at<=now()
        AND NOT EXISTS(SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws
          AND x.target_id=s.id AND x.kind='provider' AND x.completed_at IS NOT NULL)
      GROUP BY t.stage_id,s.project_id ORDER BY min(t.expires_at),t.stage_id LIMIT 50'''),
      dict(ws=workspace_id))).all()
    for stage_id,project_id in expired:
        await tombstone(session,workspace_id,project_id,stage_id,'source')
    due=(await session.execute(text(POLICY_DUE+' ORDER BY t.id LIMIT 1'),dict(ws=workspace_id))).first()
    if due:
        await tombstone(session,workspace_id,due.project_id,due.id,'source')
    # Disconnect queues every receipt for a reusable connection. Prefer a root
    # with unerased review bodies so an unrelated expired provider stage cannot
    # consume the one bounded content page.
    row=(await session.execute(text('''SELECT x.target_id,x.project_id FROM sales_content_tombstones x
      WHERE x.workspace_id=:ws AND x.kind='source' AND x.completed_at IS NULL
      ORDER BY EXISTS(
        SELECT 1 FROM xverum_tool_receipts t
        JOIN xverum_enrichment_dependencies d
          ON d.workspace_id=t.workspace_id AND d.source_id=t.id
        JOIN xverum_enrichments e
          ON e.workspace_id=d.workspace_id AND e.id=d.enrichment_id
        WHERE t.workspace_id=x.workspace_id AND t.stage_id=x.target_id
          AND e.proposal<>'{}'::jsonb
      ) DESC,x.created_at,x.id LIMIT 1'''),dict(ws=workspace_id))).first()
    if row is None:
        return 0
    ids=await purge_page(session,workspace_id,row.project_id,row.target_id)
    pending=await session.scalar(text(CLOSURE+'''SELECT EXISTS(SELECT 1 FROM xverum_stages t
      JOIN affected a ON a.id=t.id WHERE t.workspace_id=:ws AND NOT EXISTS
        (SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws AND x.target_id=t.id
         AND x.kind='provider' AND x.completed_at IS NOT NULL))'''),dict(ws=workspace_id,target=row.target_id))
    pending_enrichment=await session.scalar(text(CLOSURE+'''SELECT EXISTS(SELECT 1 FROM xverum_enrichments e
      JOIN affected a ON a.id=e.id WHERE e.workspace_id=:ws AND NOT EXISTS
        (SELECT 1 FROM sales_content_tombstones x WHERE x.workspace_id=:ws AND x.target_id=e.id
         AND x.kind='enrichment' AND x.completed_at IS NOT NULL))'''),dict(ws=workspace_id,target=row.target_id))
    if not ids and not pending and not pending_enrichment:
        await session.execute(text('''UPDATE sales_content_tombstones SET completed_at=now()
          WHERE workspace_id=:ws AND target_id=:target AND kind='source' '''),dict(ws=workspace_id,target=row.target_id))
    return len(ids)


async def revalidate_task_access(session, scope, task_id):
    from .sales_tasks import task_row, record
    from ..sales.context import resolve_context
    row=await task_row(session,scope,task_id)
    await require_current(session,scope.workspace_id,[row.id])
    current=await resolve_context(session,scope,row.source_refs)
    if current.digest!=row.context_digest:
        raise ApiError(409,'STALE_REVISION','selected context changed')
    return record(row)


async def invalidate_retained_subject(session, workspace_id, project_id, subject_id):
    """Internal native retention hook, after the canonical expiry check."""
    if project_id is None:
        return 0
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session,workspace_id)
    await tombstone(session,workspace_id,project_id,subject_id,'source')
    return len(await purge_page(session,workspace_id,project_id,subject_id))

