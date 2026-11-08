"""C61-31 bounded read-only runtime inspection. No migration or identity writes."""
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from .release_binding import database_endpoint_sha256
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, serialize_by_alias=True)


class TargetReceipt(ClosedModel):
    database: str = Field(min_length=1, max_length=63)
    endpoint_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    metadata_receipt_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class RuntimeRolePolicy(ClosedModel):
    role: str = Field(min_length=1, max_length=63)
    superuser: Literal[False] = False
    bypass_rls: Literal[False] = False


class RequiredPrivilege(ClosedModel):
    relation: str = Field(pattern=r'^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$')
    columns: list[str] = Field(min_length=1, max_length=100)
    privilege: Literal['SELECT','INSERT','UPDATE','DELETE'] = 'SELECT'


class RequiredFunction(ClosedModel):
    signature: str
    volatility: Literal['s', 'v']


class RequiredCatalogFunction(ClosedModel):
    """Explicit invoker/immutable contracts; legacy function wire shape is retained."""
    signature: str
    volatility: Literal['i','s','v']
    security_definer: StrictBool
    return_type: Literal['boolean','trigger','void']
    execute: StrictBool
    search_path: Literal['pg_catalog, public','pg_catalog, public, pg_temp'] = 'pg_catalog, public'


class RequiredTrigger(ClosedModel):
    relation: str
    name: str
    function: str
    trigger_type: Literal[11]  # ROW | BEFORE | DELETE


class SchemaContract(ClosedModel):
    contract_version: Literal['buyeros.schema-contract.v1']
    source_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    required_revisions: list[str] = Field(min_length=1, max_length=100)
    # Explicitly reviewed additive heads; unknown future heads remain blocked.
    compatible_heads: list[str] = Field(min_length=1, max_length=100)
    required_relations: dict[str, list[str]] = Field(min_length=1, max_length=100)
    required_functions: list[str | RequiredFunction] = Field(min_length=1, max_length=100)
    required_catalog_functions: list[RequiredCatalogFunction] = Field(default_factory=list, max_length=100)
    required_triggers: list[RequiredTrigger] = Field(default_factory=list, max_length=100)
    required_privileges: list[RequiredPrivilege] = Field(min_length=1, max_length=100)
    required_rls: list[str] = Field(min_length=1, max_length=100)
    runtime_role_policy: RuntimeRolePolicy
    target: TargetReceipt
    target_receipt: TargetReceipt | None = None
    evidence_mode: Literal['owned_disposable_fixture','candidate_runtime','production_readback']
    statement_timeout_ms: int = Field(default=5000, ge=100, le=10000)

    @model_validator(mode='after')
    def bounded_names(self):
        import re
        relation = re.compile(r'^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$')
        column = re.compile(r'^[a-z_][a-z0-9_]*$')
        function = re.compile(r'^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*\([a-z0-9_, ]*\)$')
        if any(not relation.fullmatch(name) or not columns or len(columns)>100
               or any(not column.fullmatch(c) for c in columns)
               for name, columns in self.required_relations.items()):
            raise ValueError('invalid relation contract')
        if any(not relation.fullmatch(name) for name in self.required_rls):
            raise ValueError('invalid RLS contract')
        if any(not function.fullmatch(name if isinstance(name, str) else name.signature)
               for name in self.required_functions):
            raise ValueError('invalid function contract')
        if any(not function.fullmatch(item.signature) for item in self.required_catalog_functions):
            raise ValueError('invalid catalog function contract')
        if any(not relation.fullmatch(item.relation) or not column.fullmatch(item.name)
               or not function.fullmatch(item.function) for item in self.required_triggers):
            raise ValueError('invalid trigger contract')
        if any(not column.fullmatch(c) for p in self.required_privileges for c in p.columns):
            raise ValueError('invalid privilege contract')
        return self


class SchemaCheck(ClosedModel):
    code: str
    passed: StrictBool


class SchemaReadiness(ClosedModel):
    schema_name: Literal['buyeros.schema-readiness.v1'] = Field(default='buyeros.schema-readiness.v1', alias='schema')
    source_sha: str
    contract_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    checked_at: datetime
    target_match: StrictBool
    observed_heads: list[str]
    compatible: StrictBool
    checks: list[SchemaCheck]
    blockers: list[str]
    evidence_mode: str


def sales_requirements(*, worker=False):
    """Source-owned minimum contract for a Task3 API readiness receipt.

    Target identity, runtime role and source SHA still come from the independently
    verified operator contract. This does not authorize a connection or migration.
    """
    common = ['id','workspace_id','created_at','updated_at']
    relations = {
        'public.sales_tasks':['id','workspace_id','project_id','thread_id','actor_id','client_message_id','intent_fingerprint',
            'message_sequence','skill_id','skill_version','state','revision','event_sequence','owner_user_id',
            'user_message','arguments','source_refs','intake_history','context_digest','output_ids','pending_review','created_at','updated_at'],
        'public.sales_task_events':common+['project_id','thread_id','task_id','sequence','kind','payload'],
        'public.sales_task_dependencies':common+['project_id','thread_id','task_id','source_id','source_version','kind','retention_class'],
        'public.conversation_thread_preferences':common+['project_id','thread_id','owner_user_id','actor_id','pinned','archived'],
        'public.conversation_threads':common+['project_id','owner_user_id','template_id','title','version','sources','runs'],
        'public.conversation_thread_messages':common+['project_id','thread_id','owner_user_id','author_user_id',
            'text','seq','role','client_message_id','turn_id','parts'],
        'public.conversation_turns':common+['project_id','thread_id','owner_user_id','actor_id','client_message_id',
            'request_fingerprint','parent_turn_id','language','skill_id','skill_version','status','step_count',
            'expected_thread_version','parts','notices'],
        'public.conversation_turn_proposals':common+['project_id','thread_id','turn_id','actor_id','capability',
            'skill_id','skill_version','title','rationale','arguments','source_refs','arguments_preview','cost',
            'requires_approval','status','revision','result'],
        'public.conversation_turn_decisions':common+['project_id','thread_id','turn_id','proposal_id','actor_id',
            'decision','request_fingerprint','continuation_turn_id','status'],
    }
    from ..db.sales_execution import SalesReview, SalesExecution, SalesStep
    from ..db.sales_outputs import SalesOutput, SalesOutputVersion, SalesOutputSection, SalesOutputDependency, SalesOutputNativeLink
    for model in (SalesReview,SalesExecution,SalesStep,SalesOutput,SalesOutputVersion,SalesOutputSection,SalesOutputDependency,SalesOutputNativeLink):
        relations['public.'+model.__tablename__]=list(model.__table__.columns.keys())
    privileges = [{'relation':name,'columns':columns,'privilege':'SELECT'} for name,columns in relations.items()]
    privileges += [{'relation':name,'columns':columns,'privilege':'INSERT'} for name,columns in relations.items()
        if name != 'public.conversation_threads']
    for name, columns in {
        'public.sales_tasks':['state','revision','event_sequence','updated_at','arguments','source_refs','intake_history','context_digest','output_ids','pending_review'],
        'public.conversation_thread_preferences':['pinned','archived','updated_at'],
        'public.conversation_threads':['version','updated_at'],
    }.items():
        privileges.append({'relation':name,'columns':columns,'privilege':'UPDATE'})
    for name,columns in {
        'public.sales_reviews':['revoked','updated_at'],
        'public.sales_executions':['calls_started','consumed_usd','unused_released','cancelled','updated_at'],
        'public.sales_steps':['state','definitely_unsubmitted','claim_id','claimed_at','usage','result_digest','native_operation_id','updated_at'],
    }.items():
        privileges.append({'relation':name,'columns':columns,'privilege':'UPDATE'})
    privileges.append({'relation':'public.conversation_threads','columns':['id'],'privilege':'DELETE'})
    privileges.append({'relation':'public.sales_outputs','columns':['revision','updated_at'],'privilege':'UPDATE'})
    privileges.append({'relation':'public.conversation_turn_proposals',
        'columns':['status','revision','result','updated_at'],'privilege':'UPDATE'})
    if worker:
        from ..db.conversation_threads import ConversationThreadShare
        relations['public.conversation_thread_shares']=list(ConversationThreadShare.__table__.columns.keys())
        # Worker grants deliberately exclude transcript and turn content; those
        # relations must not appear in the worker readiness contract either.
        for name in ('public.conversation_thread_messages', 'public.conversation_turns',
                     'public.conversation_turn_proposals', 'public.conversation_turn_decisions'):
            relations.pop(name, None)
        selected={name:columns for name,columns in relations.items()
            if name not in {'public.conversation_thread_preferences'}}
        privileges=[{'relation':name,'columns':columns,'privilege':'SELECT'} for name,columns in selected.items()]
        privileges.append({'relation':'public.sales_task_events','columns':relations['public.sales_task_events'],'privilege':'INSERT'})
        privileges.append({'relation':'public.sales_output_sections','columns':relations['public.sales_output_sections'],'privilege':'INSERT'})
        for name,columns in {
            'public.sales_tasks':['state','revision','event_sequence','updated_at'],
            'public.conversation_threads':['version'],
            'public.sales_executions':['calls_started','consumed_usd','unused_released','updated_at'],
            'public.sales_steps':['state','definitely_unsubmitted','claim_id','claimed_at','usage','result_digest','native_operation_id','updated_at'],
        }.items(): privileges.append({'relation':name,'columns':columns,'privilege':'UPDATE'})
    from ..db import xverum
    from ..db.xverum_enrichment import XverumEnrichment
    xmodels = (xverum.XverumConnection,xverum.XverumProjectAssignment,xverum.XverumCreditAccount,
        xverum.XverumCreditLimit,xverum.XverumTariff,xverum.XverumQuoteRow,xverum.XverumCreditReservation,
        xverum.XverumReceiptRow,xverum.XverumCreditSettlement,xverum.XverumStage,
        xverum.XverumToolReceipt,xverum.XverumReconciliation,XverumEnrichment)
    for model in xmodels:
        name='public.'+model.__tablename__
        relations[name]=list(model.__table__.columns.keys())
        privileges.append({'relation':name,'columns':relations[name],'privilege':'SELECT'})
    relations['public.xverum_enrichment_dependencies']=['workspace_id','enrichment_id','source_id']
    privileges.append({'relation':'public.xverum_enrichment_dependencies','columns':relations['public.xverum_enrichment_dependencies'],'privilege':'SELECT'})
    inserts=['xverum_credit_settlements']
    if not worker:
        inserts+=['xverum_enrichments','xverum_enrichment_dependencies']
        privileges.append({'relation':'public.xverum_enrichments','columns':['applied','output_revision','updated_at'],'privilege':'UPDATE'})
        inserts+=['xverum_stages','xverum_tool_receipts','xverum_reconciliations','xverum_project_assignments','xverum_quotes','xverum_credit_reservations','xverum_receipts']
        privileges.append({'relation':'public.xverum_project_assignments','columns':['id'],'privilege':'DELETE'})
        privileges.append({'relation':'public.xverum_connections','columns':['generation','version','status','configured_by','updated_at'],'privilege':'UPDATE'})
    for name in inserts:
        privileges.append({'relation':'public.'+name,'columns':relations['public.'+name],'privilege':'INSERT'})
    for name,columns in {'xverum_stages':['cancelled','updated_at'],
        'xverum_tool_receipts':['state','attempts','claim_id','request_id','credits_used','projection','projection_digest','expires_at','updated_at'],
        'xverum_credit_accounts':['updated_at'],'xverum_credit_limits':['updated_at'],
        'xverum_credit_reservations':['held_credits','updated_at'],
        'xverum_receipts':['version','outbox_id','claim_id','claimed_at','dispatch_state','request_id','projection_digest','returned_ids','updated_at']}.items():
        privileges.append({'relation':'public.'+name,'columns':columns,'privilege':'UPDATE'})
    from ..db.sales_accounting import SalesFinancialEvidence, SalesAccountingReceipt
    for model in (SalesFinancialEvidence, SalesAccountingReceipt):
        name='public.'+model.__tablename__
        relations[name]=list(model.__table__.columns.keys())
        privileges.append({'relation':name,'columns':relations[name],'privilege':'SELECT'})
        if not worker:
            privileges.append({'relation':name,'columns':relations[name],'privilege':'INSERT'})
    relations['public.sales_content_tombstones']=common+['project_id','target_id','kind','completed_at']
    privileges.append({'relation':'public.sales_content_tombstones','columns':relations['public.sales_content_tombstones'],'privilege':'SELECT'})
    privileges.append({'relation':'public.sales_content_tombstones','columns':relations['public.sales_content_tombstones'],'privilege':'INSERT'})
    privileges.append({'relation':'public.sales_content_tombstones','columns':['completed_at'],'privilege':'UPDATE'})
    if not worker:
        privileges.append({'relation':'public.sales_executions','columns':['accounting_revision','accounted_bound','settled_usd'],'privilege':'UPDATE'})
    return {'required_revisions':['0060_sales_tasks','0061_sales_outputs','0062_xverum_credits','0063_xverum_dispatch','0064_xverum_enrichment','0065_sales_lifecycle','0066_conversation_turns'], 'compatible_heads':['0066_conversation_turns'],
        'required_relations':relations, 'required_rls':list(relations),
        'required_privileges':privileges,
        'required_functions':[f'public.buyeros_{service}_receipts_writable()' for service in ('search','model','contact')],
        'required_catalog_functions':[
            {'signature':'public.buyeros_purge_xverum_enrichment(uuid)','volatility':'v',
             'security_definer':True,'return_type':'void','execute':True,'search_path':'pg_catalog, public, pg_temp'},
            {'signature':'public.buyeros_purge_xverum_stage(uuid)','volatility':'v',
             'security_definer':True,'return_type':'void','execute':True,'search_path':'pg_catalog, public, pg_temp'},
            {'signature':'public.buyeros_purge_sales_task(uuid)','volatility':'v',
             'security_definer':True,'return_type':'void','execute':True,'search_path':'pg_catalog, public, pg_temp'},
            {'signature':'public.buyeros_xverum_connections_ready()','volatility':'s',
             'security_definer':True,'return_type':'boolean','execute':True},
            {'signature':'public.buyeros_sales_event_valid(text,jsonb)','volatility':'i',
             'security_definer':False,'return_type':'boolean','execute':True},
            {'signature':'public.buyeros_sales_delete_guard()','volatility':'v',
             'security_definer':False,'return_type':'trigger','execute':False},
        ],
        'required_triggers':[{'relation':'public.conversation_threads','name':'sales_thread_delete_guard',
            'function':'public.buyeros_sales_delete_guard()','trigger_type':11}]}


def with_sales_requirements(expected: SchemaContract) -> SchemaContract:
    data = expected.model_dump(mode='json')
    required = sales_requirements(worker=expected.runtime_role_policy.role == "buyeros_worker")
    data['compatible_heads'] = required['compatible_heads']
    for relation, columns in required['required_relations'].items():
        data['required_relations'][relation] = list(dict.fromkeys(data['required_relations'].get(relation, []) + columns))
    for name in ('required_revisions','required_rls','required_functions','required_catalog_functions','required_triggers'):
        for item in required[name]:
            if item not in data[name]:
                data[name].append(item)
    privileges = {}
    for item in data['required_privileges'] + required['required_privileges']:
        key = (item['relation'],item['privilege'])
        previous = privileges.setdefault(key, {**item, 'columns':[]})
        previous['columns'] = list(dict.fromkeys(previous['columns'] + item['columns']))
    data['required_privileges'] = list(privileges.values())
    return SchemaContract.model_validate(data)


async def inspect_schema(connection: AsyncConnection, expected: SchemaContract) -> SchemaReadiness:
    """Inspect with the real runtime login and roll back all transaction settings.

    Target metadata must be independently verified by the release operator and
    bound to its immutable receipt digest. A database name alone is never proof
    of the branch. The connection endpoint is compared as an additional control.
    """
    if connection.in_transaction():
        raise ValueError('schema probe requires an idle connection')
    # Snapshot nested lists/maps too: frozen BaseModel alone is shallow.
    expected=SchemaContract.model_validate(expected.model_dump(mode='json'))
    sales = '0060_sales_tasks' in expected.required_revisions
    if sales:
        expected = with_sales_requirements(expected)
    contract_sha256=hashlib.sha256(json.dumps(expected.model_dump(mode='json',by_alias=True),
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    checks: list[SchemaCheck] = []
    heads: list[str] = []
    target_match = False
    def check(code, passed):
        checks.append(SchemaCheck(code=code, passed=bool(passed)))
    async def scalar(sql, params=None):
        return (await connection.execute(text(sql), params or {})).scalar_one()

    transaction = await connection.begin()
    try:
        await connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        await scalar("SELECT set_config('statement_timeout',:timeout,true)", {'timeout':str(expected.statement_timeout_ms)})
        metadata=(await connection.execute(text("SELECT current_database() AS database, current_user AS role, session_user AS login, current_setting('search_path') AS search_path, current_setting('server_version') AS version"))).mappings().one()
        endpoint=database_endpoint_sha256(connection.engine.url)
        target_match=(expected.target_receipt is not None and expected.target==expected.target_receipt
                      and expected.target.database==metadata['database']
                      and expected.target.endpoint_sha256==endpoint)
        check('target_unproven_or_mismatched', target_match)
        privileged=await scalar("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE pg_has_role(current_user,oid,'MEMBER') AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication))")
        check('runtime_role_mismatch', metadata['role']==metadata['login']==expected.runtime_role_policy.role)
        check('runtime_role_privileged', not privileged)
        version_oid=await scalar("SELECT to_regclass('public.alembic_version')::oid")
        readable=version_oid and await scalar("SELECT has_column_privilege(current_user,:oid,'version_num','SELECT')",{'oid':version_oid})
        check('version_metadata_unreadable',bool(readable))
        if readable:
            heads=sorted((await connection.execute(text('SELECT version_num FROM public.alembic_version LIMIT 101'))).scalars().all())
        check('schema_head_unknown', bool(heads) and len(heads)==1 and heads[0] in expected.compatible_heads)
        if sales:
            for service in ('search','model','contact'):
                check('sales_receipt_fence:'+service, await scalar(f'SELECT public.buyeros_{service}_receipts_writable()') is True)
        from alembic.script import ScriptDirectory
        from pathlib import Path
        migrations=ScriptDirectory(str(Path(__file__).resolve().parents[2]/'alembic'))
        try:
            ancestors={r.revision for head in heads for r in migrations.walk_revisions(base='base',head=head)}
        except Exception:
            ancestors=set()
        check('required_revision_unproven',set(expected.required_revisions)<=ancestors)
        for schema in sorted({name.split('.')[0] for name in expected.required_relations}):
            check('schema_usage_missing:'+schema,await scalar("SELECT has_schema_privilege(current_user,:schema,'USAGE')",{'schema':schema}))
        for name,columns in expected.required_relations.items():
            oid=await scalar('SELECT to_regclass(:name)::oid',{'name':name})
            check('relation_missing:'+name,oid is not None)
            if oid is None: continue
            check('relation_not_visible:'+name, await scalar('SELECT to_regclass(:short)::oid = :oid',{'short':name.split('.')[1],'oid':oid}) is True)
            actual=set((await connection.execute(text('SELECT attname FROM pg_catalog.pg_attribute WHERE attrelid=:oid AND attnum>0 AND NOT attisdropped'),{'oid':oid})).scalars().all())
            check('relation_columns_missing:'+name,set(columns)<=actual)
        for requirement in expected.required_privileges:
            oid=await scalar('SELECT to_regclass(:name)::oid',{'name':requirement.relation})
            allowed=bool(oid)
            if oid:
                actual=set((await connection.execute(text('SELECT attname FROM pg_catalog.pg_attribute WHERE attrelid=:oid AND attnum>0 AND NOT attisdropped'),{'oid':oid})).scalars().all())
                allowed = set(requirement.columns) <= actual
                if requirement.privilege == 'DELETE':
                    allowed = allowed and bool(await scalar("SELECT has_table_privilege(current_user,:oid,'DELETE')",{'oid':oid}))
                else:
                    for col in requirement.columns:
                        allowed=allowed and bool(await scalar("SELECT has_column_privilege(current_user,:oid,:col,:privilege)",
                            {'oid':oid,'col':col,'privilege':requirement.privilege}))
            check('privilege_missing:'+requirement.relation+':'+requirement.privilege,allowed)
        for requirement in expected.required_functions:
            # Legacy string contracts retain their original STABLE requirement.
            signature = requirement if isinstance(requirement, str) else requirement.signature
            volatility = 's' if isinstance(requirement, str) else requirement.volatility
            oid=await scalar('SELECT to_regprocedure(:signature)::oid',{'signature':signature})
            allowed=bool(oid) and await scalar("SELECT has_function_privilege(current_user,:oid,'EXECUTE')",{'oid':oid})
            check('function_missing_or_denied:'+signature,allowed)
            if oid:
                definition=(await connection.execute(text('SELECT prosecdef,proconfig,provolatile FROM pg_catalog.pg_proc WHERE oid=:oid'),{'oid':oid})).one()
                check('function_contract_mismatch:'+signature, definition[0] and 'search_path=pg_catalog, public' in (definition[1] or []) and definition[2]==volatility)
        for requirement in expected.required_catalog_functions:
            oid = await scalar('SELECT to_regprocedure(:signature)::oid', {'signature':requirement.signature})
            allowed = bool(oid)
            if oid and requirement.execute:
                allowed = bool(await scalar("SELECT has_function_privilege(current_user,:oid,'EXECUTE')",{'oid':oid}))
            check('function_missing_or_denied:'+requirement.signature, allowed)
            if oid:
                definition = (await connection.execute(text(
                    'SELECT prosecdef,proconfig,provolatile,prorettype::regtype::text FROM pg_catalog.pg_proc WHERE oid=:oid'),{'oid':oid})).one()
                check('function_contract_mismatch:'+requirement.signature,
                    definition[0] == requirement.security_definer and f'search_path={requirement.search_path}' in (definition[1] or [])
                    and definition[2] == requirement.volatility and definition[3] == requirement.return_type)
        for requirement in expected.required_triggers:
            valid = await scalar("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger
                WHERE tgrelid=to_regclass(:relation) AND tgname=:name AND NOT tgisinternal
                AND tgenabled IN ('O','A') AND tgtype=:kind AND tgfoid=to_regprocedure(:function)
                AND tgqual IS NULL AND tgnargs=0)""",
                {'relation':requirement.relation,'name':requirement.name,'kind':requirement.trigger_type,'function':requirement.function})
            check('trigger_missing_or_disabled:'+requirement.relation+':'+requirement.name, valid)
        if sales:
            # Verify the validator is actually attached; never execute a trigger or probe write.
            valid = await scalar("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_constraint c
                JOIN pg_catalog.pg_depend d ON d.classid='pg_constraint'::regclass AND d.objid=c.oid
                AND d.refclassid='pg_proc'::regclass
                AND d.refobjid=to_regprocedure('public.buyeros_sales_event_valid(text,jsonb)')
                WHERE c.conrelid=to_regclass('public.sales_task_events') AND c.contype='c' AND c.convalidated
                AND pg_get_expr(c.conbin,c.conrelid) LIKE '% IS TRUE%')""")
            check('sales_event_validation_constraint_missing', valid)
        for name in expected.required_rls:
            state=(await connection.execute(text('SELECT relrowsecurity,relforcerowsecurity FROM pg_catalog.pg_class WHERE oid=to_regclass(:name)'),{'name':name})).one_or_none()
            check('rls_not_forced:'+name,state is not None and state[0] and state[1])
    except Exception:
        # Driver messages can contain credentials, identity binds or SQL. Do not
        # serialize them. Unknown failures are incompatible, never a green probe.
        check('schema_probe_failed',False)
    finally:
        await transaction.rollback()
    blockers=[c.code for c in checks if not c.passed]
    return SchemaReadiness(source_sha=expected.source_sha,contract_sha256=contract_sha256,checked_at=datetime.now(timezone.utc),
        target_match=target_match,observed_heads=heads,compatible=not blockers,
        checks=checks,blockers=blockers,evidence_mode=expected.evidence_mode)
