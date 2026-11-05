"""Explicit current approved facts and saved revisions. No sibling transcripts or Drive bodies."""
import hashlib
import json
import re
from sqlalchemy import select
from ..db.models import Membership
from ..db.icp import Project
from ..api.deps import permission_for_roles
from ..services.conversation_reply import resolve_sources
from .contracts import ContextSnapshot, Scope, SourceRef


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def durable_refs(refs):
    refs = tuple(SourceRef.model_validate(ref) for ref in refs)
    if len(refs) > 20 or len({(ref.kind, ref.id) for ref in refs}) != len(refs):
        raise ValueError('bounded unique selected sources required')
    for ref in refs:
        if ref.retention_class != 'durable' or ref.kind not in {'project_fact', 'document', 'output', 'provider_evidence','buyer','profile','run'}:
            raise ValueError('source is not eligible for durable sales context')
        expected = ref.kind + ':' + str(ref.id) if ref.kind in {'document','output','provider_evidence','buyer','profile','run'} else None
        if expected is not None and ref.locator != expected:
            raise ValueError('noncanonical selected locator')
        if ref.kind == 'project_fact' and not re.fullmatch(r'fact:profile:[a-f0-9-]{36}:' + str(ref.id), ref.locator):
            raise ValueError('noncanonical selected fact locator')
    return refs


async def require_scope(session, scope):
    member = (await session.execute(select(Membership).where(Membership.workspace_id == scope.workspace_id,
        Membership.user_id == scope.actor_id, Membership.active.is_(True)))).scalar_one_or_none()
    project = (await session.execute(select(Project).where(Project.workspace_id == scope.workspace_id,
        Project.id == scope.project_id, Project.status == 'active'))).scalar_one_or_none()
    if member is None or not permission_for_roles(member.roles, 'getProject') or project is None:
        raise ValueError('current sales source authority unavailable')


def snapshot_from_sources(refs, sources, profile_version, profile_hash, connection_generations=None):
    refs = durable_refs(refs)
    data = {'refs':[ref.model_dump(mode='json') for ref in refs], 'sources':sources,
            'profile_version':profile_version, 'profile_hash':profile_hash}
    if connection_generations:
        data['connection_generations']={str(k):v for k,v in connection_generations.items()}
    snapshot = ContextSnapshot(refs=refs, digest=digest(data), profile_version=profile_version,
        connection_generations=connection_generations or {})
    snapshot._sources = sources
    snapshot._profile_hash = profile_hash
    return snapshot


def empty_context():
    return snapshot_from_sources([], [], None, '')


async def resolve_context(session, scope: Scope, refs: list[SourceRef], *, _seen=frozenset(), _budget=None,
                          _enrichment_id=None) -> ContextSnapshot:
    if _budget is None: _budget=[0]
    refs = durable_refs(refs)  # Reject mixed/Drive before any content materialization.
    await require_scope(session, scope)
    from ..services.sales_retention import require_current
    await require_current(session,scope.workspace_id,[ref.id for ref in refs])
    if not refs:
        return empty_context()
    if any(ref.kind in {'output','provider_evidence','buyer','profile','run'} for ref in refs):
        from ..services.xverum_dispatch import gates
        await gates(session,scope.workspace_id)
    native = [ref for ref in refs if ref.kind not in {'output','provider_evidence','buyer','profile','run'}]
    grounding = await resolve_sources(session, workspace_id=scope.workspace_id,
        project_id=scope.project_id, source_ids=[ref.locator for ref in native], readonly=True) if native else None
    # Version is the current approved offer revision, pinned alongside the profile hash.
    if grounding and any(ref.version != grounding.offer_revision for ref in native):
        raise ValueError('selected source version changed')
    if grounding and len(grounding.sources) != len(native):
        raise ValueError('selected source set changed')
    sources = [];generations={}
    by_locator={s['citation']['id']:s for s in grounding.sources} if grounding else {}
    for ref in refs:
        native_proof=None
        if ref.kind in {'buyer','profile','run'}:
            from .native_sources import resolve_native_source
            effective=ref
            if _enrichment_id is not None:
                from ..services.xverum_enrichment import transition_native_source
                effective=await transition_native_source(session,scope,_enrichment_id,ref)
            excerpts,native_proof=await resolve_native_source(session,scope,effective)
        elif ref.kind == 'provider_evidence':
            from ..services.xverum_dispatch import resolve_evidence
            value=await resolve_evidence(session,scope,ref,_enrichment_id=_enrichment_id)
            generations[value['connection_id']]=value['connection_generation']
            body=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            if len(body)>12000: raise ValueError('provider evidence exceeds selected context bound')
            excerpts=[body[i:i+800] for i in range(0,len(body),800)]
        elif ref.kind == 'output':
            from ..services.sales_outputs import get_output
            output=await get_output(session,scope,ref.id,ref.version,_seen=_seen,_budget=_budget)
            if output.availability!='available': raise ValueError('selected output dependencies unavailable')
            body=json.dumps(output.content.model_dump(mode='json'),sort_keys=True,ensure_ascii=False,separators=(',',':'))
            if len(body)>12000: raise ValueError('selected output exceeds context bound; select a smaller revision')
            excerpts=[body[i:i+800] for i in range(0,len(body),800)]
        else:
            if ref.locator not in by_locator: raise ValueError('selected source identity changed')
            excerpts=by_locator[ref.locator]['excerpts']
        entry={'ref':ref.model_dump(mode='json'),'excerpts':excerpts}
        if native_proof is not None: entry['native_proof']=native_proof
        sources.append(entry)
    return snapshot_from_sources(refs,sources,grounding.offer_revision if grounding else None,grounding.profile_hash if grounding else '',generations)
