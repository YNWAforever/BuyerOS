"""Sales-only reviewed dispatch selection. No environment variable selects a registration."""
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID
import os
from types import MappingProxyType
from ..providers.base import activation_blockers
from ..api.errors import ApiError
from .model import ROUTE, PROMPT_VERSION

REGISTRATION = None
# Task6 supplies DB-only storage; accounting and reviewed live selection remain separate.
# Its save_section(session, scope, parent, step, basis, candidate) runs in the receipt
# transaction and must do DB-only work. Canonical assembly/readback remains separate.
from ..services.sales_outputs import SECTION_OWNER
# Future provider/native owners may supply nonbillable readback, never blind resubmit.
RECONCILER = None


class ParentAccountingOwner(Protocol):
    async def reconcile_parent(self, engine, *, scope, execution_id: UUID,
                               evidence_ids: tuple[UUID, ...], expected_revision: int, key: str) -> UUID:
        """Task14: return durable reconciliation receipt ID, never a per-child settlement.

        Load parent/reservation and authoritative child/provider evidence by identity;
        bind workspace, claim, provider account, currency and pricing. Lock policy,
        budget, thread, parent/children then reservation; deduplicate evidence and CAS
        accounting revision. Atomically settle the parent exactly once and release
        proven unused liability only. Unknown charges retain their hold. Retain the
        minimal financial evidence/receipt independently of private-content purge. Token usage
        is not USD evidence. No external IO inside the accounting transaction.
        """
        ...


from ..services.sales_accounting import ACCOUNTING_OWNER  # DB-only, distinct from live selection


class ContactEnrichmentOwner:
    """Explicit reviewed DB-only skill actions; no model/provider activation."""
    async def propose(self,session,scope,buyer_id,receipt_ids,*,task_id=None,selected_id=None,previous_proposal_id=None):
        from ..services.xverum_enrichment import propose_enrichment
        return await propose_enrichment(session,scope,buyer_id,receipt_ids,task_id=task_id,selected_id=selected_id,previous_proposal_id=previous_proposal_id)

    async def apply(self,session,scope,proposal_id,fields,expected_revision,key):
        from ..services.xverum_enrichment import apply_enrichment
        return await apply_enrichment(session,scope,proposal_id,fields,expected_revision,key)


CONTACT_ENRICHMENT_OWNER=ContactEnrichmentOwner()


class CoreSkillOwner:
    """Explicit nonbillable producer; does not select or replace model dispatch."""
    async def candidate(self,session,scope,row):
        from .research import candidate_for
        return await candidate_for(session,scope,row)

    async def guidance(self,session,scope,row):
        from .research import guidance
        return await guidance(session,scope,row)


CORE_SKILL_OWNER=CoreSkillOwner()


class DocumentSkillOwner:
    """Explicit server producer over authorized native records; no client candidate."""
    async def candidate(self,session,scope,row):
        from .documents import candidate_for
        return await candidate_for(session,scope,row)


DOCUMENT_SKILL_OWNER=DocumentSkillOwner()


@dataclass(frozen=True)
class DefinitelyUnsubmitted:
    code: str = 'configuration_required'


def valid_credential(key):
    return isinstance(key,str) and 1 <= len(key) <= 4096 and all(33 <= ord(c) <= 126 for c in key)

def credential_ready():
    return valid_credential(os.environ.get('BUYEROS_OPENCODE_API_KEY'))

# These actions prepare model sections only. No native mutation or nested dispatch.
ACTIONS = MappingProxyType({name: 'model_sections' for name in (
    'tasks.plan', 'research.read', 'profile.propose', 'drafts.prepare', 'documents.prepare')})


def action(name):
    if name not in ACTIONS:
        raise ValueError('action owner is not registered for sales execution')
    return ACTIONS[name]


def selected(market, language):
    from ..settings import get_settings
    from ..execution.config import get_settings as execution_settings
    item = REGISTRATION
    if (item is None or SECTION_OWNER is None or ACCOUNTING_OWNER is None
        or not callable(getattr(ACCOUNTING_OWNER,'reconcile_parent',None))
        or not credential_ready() or not get_settings().paid_admission_enabled
        or not execution_settings().paid_dispatch_enabled
        or item.model_route != replace(ROUTE, route_id=PROMPT_VERSION)
        or item.capability.provider != 'opencode-go' or item.capability.service != 'model'
        or not item.policy_binding or not item.sandbox_evidence
        or item.capability.max_liability is None
        or item.capability.max_liability.currency != 'USD'
        or activation_blockers(item.capability,market=market,language=language,role='company')):
        raise ApiError(503,'SALES_MODEL_UNAVAILABLE','reviewed sales model configuration is required')
    return item


async def complete(basis, item):
    """Production transport bridge; invoked only after a durable sales claim commits."""
    import os
    import httpx
    from ..providers.opencode_model import OpenCodeGoModelClient
    key = os.environ.get('BUYEROS_OPENCODE_API_KEY')
    if not valid_credential(key):
        return DefinitelyUnsubmitted()
    async with httpx.AsyncClient() as http:
        client = OpenCodeGoModelClient(api_key=key,http=http,model_id=item.model_id)
        return await client.complete(basis,item.model_route)
