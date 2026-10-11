"""Project work summary and list predicates over current durable tenant data."""
from sqlalchemy import and_,func,or_,select
from ..db.buyers import ProjectBuyer
from ..db.drafts import DraftRevision,OutreachDraft
from ..db.outbox import AsyncJob
from ..db.contact import EnrichmentJob,EnrichmentQuote,ProviderOperation
from ..db.budget import BudgetAccount,BudgetReservation,BudgetReservationAllocation
from ..db.runs import SearchRun
from .buyer_selection import selection_query

def async_job_conditions(*,workspace_id,member,project_id=None,status=None):
 conditions=[AsyncJob.workspace_id==workspace_id]
 if 'workspace_admin' not in member['roles']:conditions.append(AsyncJob.actor_user_id==member['user_id'])
 if project_id is not None:conditions.append(AsyncJob.project_id==project_id)
 if status is not None:conditions.append(AsyncJob.status==status)
 return conditions

def draft_list_query(*,workspace_id,project_id,approval=None):
 query=select(OutreachDraft,DraftRevision).join(DraftRevision,
  (DraftRevision.workspace_id==OutreachDraft.workspace_id)&(DraftRevision.draft_id==OutreachDraft.id)&(DraftRevision.revision_number==OutreachDraft.current_revision))
 query=query.where(OutreachDraft.workspace_id==workspace_id,OutreachDraft.project_id==project_id)
 if approval=='pending':query=query.where(OutreachDraft.state=='review_requested')
 return query

def provider_operations_query(*,workspace_id,project_id,member,acceptance=None):
 # Contact receipts belong to enrichment jobs, never AsyncJob. A present buyer
 # must agree with the quote project; no email, untrusted URL or intent parsing.
 buyer_matches=select(ProjectBuyer.id).where(ProjectBuyer.workspace_id==workspace_id,
  ProjectBuyer.id==ProviderOperation.buyer_id,ProjectBuyer.project_id==project_id).correlate(ProviderOperation).exists()
 contact=select(EnrichmentJob.id).join(EnrichmentQuote,
  (EnrichmentQuote.workspace_id==EnrichmentJob.workspace_id)&(EnrichmentQuote.id==EnrichmentJob.quote_id)).where(
  EnrichmentJob.workspace_id==workspace_id,EnrichmentJob.id==ProviderOperation.job_id,
  EnrichmentQuote.project_id==project_id,or_(ProviderOperation.buyer_id.is_(None),buyer_matches))
 if 'workspace_admin' not in member['roles']:contact=contact.where(EnrichmentQuote.actor_id==member['user_id'])
 contact=contact.correlate(ProviderOperation).exists()
 # Research has no enrichment job. Its actual operation hold links a run
 # allocation and the immutable project's allocation. Missing provenance is
 # excluded, rather than silently borrowing the selected project or actor.
 project_allocation=select(BudgetReservationAllocation.id).join(BudgetAccount,
  (BudgetAccount.workspace_id==BudgetReservationAllocation.workspace_id)&(BudgetAccount.id==BudgetReservationAllocation.account_id)).where(
  BudgetReservationAllocation.workspace_id==workspace_id,BudgetReservationAllocation.reservation_id==BudgetReservation.id,
  BudgetAccount.scope=='project',BudgetAccount.scope_id==project_id).correlate(BudgetReservation).exists()
 research=select(BudgetReservation.id).join(BudgetReservationAllocation,
  (BudgetReservationAllocation.workspace_id==BudgetReservation.workspace_id)&(BudgetReservationAllocation.reservation_id==BudgetReservation.id)).join(BudgetAccount,
  (BudgetAccount.workspace_id==BudgetReservationAllocation.workspace_id)&(BudgetAccount.id==BudgetReservationAllocation.account_id)).join(SearchRun,
  (SearchRun.workspace_id==BudgetAccount.workspace_id)&(SearchRun.id==BudgetAccount.scope_id)).where(
  BudgetReservation.workspace_id==workspace_id,BudgetReservation.operation_id==ProviderOperation.id,
  BudgetAccount.scope=='run',SearchRun.project_id==project_id,project_allocation)
 if 'workspace_admin' not in member['roles']:research=research.where(SearchRun.execution_snapshot['actor_id'].astext==str(member['user_id']))
 research=research.correlate(ProviderOperation).exists()
 query=select(ProviderOperation).where(ProviderOperation.workspace_id==workspace_id,
  or_(contact,and_(ProviderOperation.job_id.is_(None),research)))
 if acceptance=='unknown':query=query.where(ProviderOperation.status.in_(['unknown','submitting']))
 return query

def count_query(query):return select(func.count()).select_from(query.order_by(None).subquery())

async def read_work_queue(session,*,workspace_id,project_id,member):
 queries=[]
 for filters in [{'review':['awaiting_review']},{'owner_unassigned':True},{'unknown_fit':True}]:
  queries.append(await selection_query(session,workspace_id=workspace_id,project_id=project_id,filters=filters,sort='best_fit'))
 pending=draft_list_query(workspace_id=workspace_id,project_id=project_id,approval='pending')
 failed=select(AsyncJob.id).where(*async_job_conditions(workspace_id=workspace_id,project_id=project_id,member=member,status='failed'))
 unknown=provider_operations_query(workspace_id=workspace_id,project_id=project_id,member=member,acceptance='unknown')
 kinds=[('awaiting_review',{'review':'awaiting_review'}),('pending_approval',{'approval':'pending'}),('unassigned',{'queue':'unassigned'}),('failed_job',{'status':'failed'}),('unknown_fit',{'queue':'unknown'}),('unknown_acceptance',{'acceptance':'unknown'})]
 # One statement gives every card the same MVCC observation and server clock.
 ordered=[queries[0],pending,queries[1],failed,queries[2],unknown]
 row=(await session.execute(select(func.statement_timestamp(),*[count_query(q).scalar_subquery() for q in ordered]))).one()
 return {'as_of':row[0].isoformat(),'items':[{'kind':kind,'count':int(row[i+1]),'filters':filters} for i,(kind,filters) in enumerate(kinds)]}

def provider_operation_data(row):
 return {'id':str(row.id),'status':row.status,'capability':row.capability,'created_at':row.created_at.isoformat(),'updated_at':row.updated_at.isoformat()}
