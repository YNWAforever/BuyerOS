"""C61-31 bounded read-only runtime inspection. No migration or identity writes."""
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
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
    privilege: Literal['SELECT'] = 'SELECT'


class SchemaContract(ClosedModel):
    contract_version: Literal['buyeros.schema-contract.v1']
    source_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    required_revisions: list[str] = Field(min_length=1, max_length=100)
    # Explicitly reviewed additive heads; unknown future heads remain blocked.
    compatible_heads: list[str] = Field(min_length=1, max_length=100)
    required_relations: dict[str, list[str]] = Field(min_length=1, max_length=100)
    required_functions: list[str] = Field(min_length=1, max_length=100)
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
        if any(not function.fullmatch(name) for name in self.required_functions):
            raise ValueError('invalid function contract')
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
        endpoint=hashlib.sha256(f'{connection.engine.url.host}:{connection.engine.url.port or 5432}'.encode()).hexdigest()
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
                for col in requirement.columns:
                    allowed=allowed and col in actual and bool(await scalar("SELECT has_column_privilege(current_user,:oid,:col,'SELECT')",{'oid':oid,'col':col}))
            check('privilege_missing:'+requirement.relation+':'+requirement.privilege,allowed)
        for signature in expected.required_functions:
            oid=await scalar('SELECT to_regprocedure(:signature)::oid',{'signature':signature})
            allowed=bool(oid) and await scalar("SELECT has_function_privilege(current_user,:oid,'EXECUTE')",{'oid':oid})
            check('function_missing_or_denied:'+signature,allowed)
            if oid:
                definition=(await connection.execute(text('SELECT prosecdef,proconfig,provolatile FROM pg_catalog.pg_proc WHERE oid=:oid'),{'oid':oid})).one()
                check('function_contract_mismatch:'+signature, definition[0] and 'search_path=pg_catalog, public' in (definition[1] or []) and definition[2]=='s')
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
