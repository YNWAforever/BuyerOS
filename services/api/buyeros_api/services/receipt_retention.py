"""Bounded tenant payload erasure; acceptance hashes/holds never change."""
from datetime import datetime,timezone
import re,uuid
from sqlalchemy import text

SERVICES=('search','model','contact')

def redacted_receipt(row,*,response_key='response'):
    if row is None:return None
    state=('redacted' if row.get('redacted_at') is not None else
           'expired' if row.get('dependency_expired') is True or
             (row.get('retention_until') is not None and row['retention_until']<=datetime.now(timezone.utc)) else None)
    if state is not None:
        result={'ref':str(row['id']),'request':None,'state':state,'digest':row['response_hash']}
        result[response_key]=[] if response_key=='sources' else None
        return result
    return None

async def require_current_receipt_read(session,*,workspace_id,actor_id,project_id):
    from sqlalchemy import select
    from ..db.models import Membership
    from ..db.icp import Project
    from ..api.deps import permission_for_roles
    from .policy_service import evaluate_current_policy_readonly
    member=(await session.execute(select(Membership).where(Membership.workspace_id==workspace_id,Membership.user_id==actor_id,Membership.active.is_(True)))).scalar_one_or_none()
    project=(await session.execute(select(Project).where(Project.workspace_id==workspace_id,Project.id==project_id,Project.status=='active'))).scalar_one_or_none()
    if member is None or not permission_for_roles(member.roles,'startRun') or project is None:raise ValueError('current receipt read permission unavailable')
    policy=await evaluate_current_policy_readonly(session,{'workspace_id':workspace_id,'project_id':project_id},'account_research',datetime.now(timezone.utc))
    if not policy['allowed']:raise ValueError('current receipt purpose policy unavailable')

async def bind_receipt_source(session,*,service,receipt_id,source_id):
    if service not in SERVICES or not isinstance(receipt_id,uuid.UUID) or not isinstance(source_id,uuid.UUID):raise ValueError('canonical current receipt/source required')
    await session.execute(text("""INSERT INTO receipt_source_bindings(id,workspace_id,source_id,service,receipt_id)
      VALUES(:id,current_setting('app.workspace_id',true)::uuid,:source,:service,:receipt)
      ON CONFLICT(workspace_id,source_id,service,receipt_id) DO NOTHING"""),
      {'id':uuid.uuid4(),'source':source_id,'service':service,'receipt':receipt_id})

async def expire_provider_receipts(session,*,now,policy_version,limit=50,source_id=None):
    if (not isinstance(now,datetime) or now.tzinfo is None or not isinstance(policy_version,str) or
        not re.fullmatch(r'[A-Za-z0-9._-]{1,64}',policy_version) or type(limit) is not int or not 1<=limit<=100 or
        (source_id is not None and not isinstance(source_id,uuid.UUID))):raise ValueError('explicit finite receipt retention policy/count/time required')
    expired=[]
    for service in SERVICES:
        remaining=limit-len(expired)
        if remaining<=0:break
        table=service+'_receipts';payload='response_ciphertext' if service=='contact' else 'response'
        rows=(await session.execute(text(f"""SELECT id,workspace_id FROM {table} r WHERE (
          (redacted_at IS NULL AND (retention_until<=LEAST(:now,now()) OR public.buyeros_receipt_dependency_expired(workspace_id,:service,id,request)))
          OR (:service='search' AND redacted_at IS NOT NULL AND CAST(:source AS uuid) IS NOT NULL))
          AND (CAST(:source AS uuid) IS NULL OR EXISTS(SELECT 1 FROM receipt_source_bindings b WHERE b.workspace_id=r.workspace_id AND b.receipt_id=r.id AND b.service=:service AND b.source_id=:source)
            OR (:service='model' AND EXISTS(SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(request#>'{{basis,evidence}}')='array' THEN request#>'{{basis,evidence}}' ELSE '[]'::jsonb END) e WHERE e->>'source_id'=CAST(:source AS text))))
          ORDER BY retention_until,id LIMIT :limit"""),{'now':now,'service':service,'source':source_id,'limit':remaining})).mappings().all()
        for row in rows:
            erased=(await session.execute(text("SELECT public.buyeros_erase_provider_receipt(:ws,:service,:id,:policy)"),{'ws':row['workspace_id'],'service':service,'id':row['id'],'policy':policy_version})).scalar_one()
            if not erased:continue
            expired.append({'service':service,'id':str(row['id'])})
    return expired
