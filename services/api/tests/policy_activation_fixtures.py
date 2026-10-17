"""Synthetic controller identities. No real company/workspace/consent packet."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5, NAMESPACE_URL
from urllib.parse import urlsplit
import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from . import auth_fixtures as fx
from .conftest import runtime_role_dsn
from .policy_activation_target import assert_owned_test_dsn
from .test_policy_activation_contract import terms_body, W, P


@pytest.fixture
def policy_case(isolated_seeded):
    assert_owned_test_dsn(isolated_seeded)
    now = datetime.now(timezone.utc)
    actors = {role: uuid5(NAMESPACE_URL, "owned-policy-" + role) for role in
              ("owner", "requester", "unqualified", "viewer", "operator", "reviewer", "revoked", "foreign")}
    subjects = {role: "auth0|owned-policy-" + role for role in actors}
    with psycopg.connect(isolated_seeded) as db:
        for role, actor in actors.items():
            workspace = "22222222-2222-4222-8222-222222222222" if role == "foreign" else W
            actual_role = role if role in {"viewer", "operator", "reviewer"} else "workspace_admin"
            db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s)", (actor, fx.ISSUER, subjects[role]))
            # The current identity migration synchronizes the canonical binding
            # from users; use that real trigger rather than duplicating its row.
            assert db.execute("SELECT user_id FROM user_identities WHERE issuer=%s AND subject=%s",
                              (fx.ISSUER, subjects[role])).fetchone() == (actor,)
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES(%s,%s,%s,%s,%s,1)",
                       (uuid5(NAMESPACE_URL, "membership-" + role), workspace, actor, [actual_role], role != "revoked"))
    return {"dsn": isolated_seeded, "workspace": UUID(W), "project": UUID(P),
            "actors": actors, "subjects": subjects, "now": now}


def owner_run(case, work, *, runtime=False, read_only=False):
    dsn = case["dsn"]
    assert_owned_test_dsn(dsn)
    if runtime not in (False, True, "transaction_role"):
        raise ValueError("explicit fixture runtime connection mode required")
    if runtime is True:
        dsn = runtime_role_dsn(dsn)
        assert urlsplit(dsn).username == "buyeros_api", "runtime fixture must never silently use its owner"
    async def run():
        from buyeros_api.db.session import tenant_session
        engine = create_async_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1), poolclass=NullPool)
        try:
            async with tenant_session(engine, case["workspace"], read_only=read_only) as session:
                if runtime == "transaction_role":
                    from sqlalchemy import text
                    # A transient reduction to an existing role, not a LOGIN,
                    # password, GRANT or persistent security-setting change.
                    await session.execute(text("SET LOCAL ROLE buyeros_api"))
                    actual = (await session.execute(text(
                        "SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
                    if tuple(actual) != ("buyeros_api", False, False):
                        raise ValueError("actual least-privilege fixture role required")
                return await work(session)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def manifest_body(case):
    from sqlalchemy.engine import make_url
    from buyeros_api.services.release_binding import database_target_sha256
    return {
        "schema_version": "buyeros.policy-authority.v1",
        "operation": "provision",
        "workspace_id": str(case["workspace"]), "project_id": str(case["project"]),
        "approver_user_id": str(case["actors"]["owner"]), "membership_version": case.get("membership_version", 1),
        "purposes": ["account_research", "contact_research", "draft_preparation"],
        "allowed_actions": [
            "observation.append", "lead.review", "lead.evidence.read", "preparation.create",
            "preparation.revise", "preparation.request_review", "preparation.review", "preparation.read",
        ],
        "valid_from": (case["now"] - timedelta(days=1)).isoformat(),
        "expires_at": (case["now"] + timedelta(days=30)).isoformat(),
        "designation_reference": "fixture://designation/not-real-consent",
        "designation_sha256": "a" * 64, "source_sha": "1" * 40,
        "target_sha256": database_target_sha256(make_url(case["dsn"])),
        "expected_authority_id": None, "expected_authority_version": None,
    }


def provision_fixture_authority(case):
    from buyeros_api.services import policy_activation_bootstrap as service
    manifest = service.AuthorityManifest.model_validate(manifest_body(case))
    authorization = service.BootstrapAuthorization(
        manifest_sha256=service.manifest_digest(manifest), target_sha256=manifest.target_sha256,
        source_sha=manifest.source_sha, approval_reference="fixture://approved-local-run",
        approval_evidence_sha256="b" * 64,
    )
    async def run(session):
        execution = await service.verify_bootstrap_execution(session, manifest, authorization)
        return await service.apply_authority_manifest(session, manifest, execution, case["now"])
    return owner_run(case, run)


def current_terms(case, purpose="contact_research"):
    body = terms_body()
    body.update(workspace_id=str(case["workspace"]), controller_scope_id=str(case["workspace"]),
                project_id=str(case["project"]), purpose=purpose,
                valid_from=(case["now"] - timedelta(days=1)).isoformat(),
                expires_at=(case["now"] + timedelta(days=14)).isoformat())
    return body


def approve_native_fixture(dsn, workspace, project, owner, *, domains=("rice.example.test",),
                           documents=(), purposes=("account_research", "contact_research", "draft_preparation"),
                           provider_scope=None, research_scope=None, actions=None, transaction_role=False, countries=None,
                           terms_overrides=None):
    """Real bootstrap + request + decision, only in the gated synthetic database."""
    assert_owned_test_dsn(dsn)
    from uuid import uuid4
    from buyeros_api.api.policy_activation_schemas import ActivationSubmit, ActivationDecision, PolicyTerms
    from buyeros_api.services import policy_activation_service as service
    case = {"dsn": dsn, "workspace": UUID(str(workspace)), "project": UUID(str(project)),
            "actors": {"owner": UUID(str(owner))}, "now": datetime.now(timezone.utc)}
    from buyeros_api.api.policy_activation_schemas import MANUAL_ACTIONS
    wanted_actions = sorted(actions if actions is not None else MANUAL_ACTIONS)
    with psycopg.connect(dsn) as db:
        existing = db.execute(
            "SELECT id,version,membership_version,allowed_actions,purposes FROM policy_controller_authorities WHERE workspace_id=%s AND project_id=%s "
            "AND approver_user_id=%s ORDER BY version DESC LIMIT 1", (workspace, project, owner)).fetchone()
        membership_version = db.execute("SELECT version FROM memberships WHERE workspace_id=%s AND user_id=%s "
                                        "AND active AND 'workspace_admin'=ANY(roles)", (workspace, owner)).fetchone()
        if membership_version is None:
            raise ValueError("synthetic owner must have a current real admin membership")
        case["membership_version"] = membership_version[0]
    receipt = {"authority_id": str(existing[0]), "authority_version": existing[1]} if existing else None
    if (not existing or existing[2] != case["membership_version"]
            or not set(wanted_actions) <= set(existing[3]) or not set(purposes) <= set(existing[4])):
        from buyeros_api.services import policy_activation_bootstrap as bootstrap
        manifest = bootstrap.AuthorityManifest.model_validate({
            **manifest_body(case), "expected_authority_id": str(existing[0]) if existing else None,
            "expected_authority_version": existing[1] if existing else None,
            "allowed_actions": sorted(set(wanted_actions) | set(existing[3] if existing else MANUAL_ACTIONS)),
            "purposes": sorted(set(purposes) | set(existing[4] if existing else manifest_body(case)["purposes"])),
        })
        authorization = bootstrap.BootstrapAuthorization(
            manifest_sha256=bootstrap.manifest_digest(manifest), target_sha256=manifest.target_sha256,
            source_sha=manifest.source_sha, approval_reference="fixture://current-membership-redesignation",
            approval_evidence_sha256="b" * 64)
        async def redesignate(session):
            execution = await bootstrap.verify_bootstrap_execution(session, manifest, authorization)
            return await bootstrap.apply_authority_manifest(session, manifest, execution, case["now"])
        receipt = owner_run(case, redesignate)
    actor = service.PolicyActor(case["workspace"], case["actors"]["owner"], frozenset({"workspace_admin"}), case["membership_version"])
    async def activate(session):
        for purpose in purposes:
            from buyeros_api.services.policy_activation_read import latest_head
            head = await latest_head(session, workspace_id=case["workspace"], project_id=case["project"], purpose=purpose)
            body = current_terms(case, purpose)
            body["allowed_sources"] = {"domains": list(domains), "document_ids": [str(v) for v in documents]}
            body["retention_days"] = 90
            if countries is not None:
                body["countries"] = list(countries)
            body["allowed_actions"] = wanted_actions
            if provider_scope is not None:
                body.update(template_version="provider-native.v1", provider_scope=provider_scope)
            if research_scope is not None:
                body.update(template_version="provider-research.v1", research_scope=research_scope)
            body.update(terms_overrides or {})
            checked=PolicyTerms.model_validate(body)
            request = await service.submit_activation(session, actor=actor, data=ActivationSubmit(
                client_request_id=uuid4(), authority_id=receipt["authority_id"],
                authority_version=receipt.get("authority_version", receipt.get("version", 1)),
                expected_policy_id=head.id if head else None, expected_policy_version=head.version if head else None, terms=body,
                request_deadline=min(case["now"] + timedelta(days=2),checked.expires_at),
            ), key=str(uuid4()), now=case["now"])
            await service.decide_activation(session, actor=actor, request_id=request.id, data=ActivationDecision(
                action="approve", terms_hash=request.terms_hash,
                expected_policy_id=head.id if head else None, expected_policy_version=head.version if head else None,
                reason="Owned synthetic workflow; mock transport only; no real processing or sending.",
            ), key=str(uuid4()), now=case["now"])
    owner_run(case, activate, runtime="transaction_role" if transaction_role else True)


def approve_provider_fixture(dsn, workspace, project, owner, *, purpose, scope, domains, actions=None,
                             transaction_role=False):
    """Explicit opt-in provider designation and real controlled approval; owned DB only."""
    from buyeros_api.api.policy_activation_schemas import PROVIDER_ACTIONS
    defaults = ("contact.enrich",) if purpose == "contact_research" else PROVIDER_ACTIONS[purpose]
    return approve_native_fixture(dsn, workspace, project, owner, domains=domains,
        purposes=(purpose,), provider_scope=scope, actions=sorted(defaults if actions is None else actions),
        transaction_role=transaction_role)


def ensure_fixture_controller(dsn, workspace, project):
    """Create only synthetic data records in a verified disposable namespace."""
    assert_owned_test_dsn(dsn)
    user = uuid5(NAMESPACE_URL, f"owned-policy-controller:{workspace}:{project}")
    with psycopg.connect(dsn) as db:
        owner = db.execute("SELECT current_user,pg_get_userbyid(relowner) FROM pg_class "
                           "WHERE oid='public.policy_controller_authorities'::regclass").fetchone()
        if not owner or owner[0] != owner[1] or owner[0] in {"buyeros_api", "buyeros_worker"}:
            raise ValueError("owned migration-owner fixture connection required")
        existing = db.execute("SELECT user_id FROM memberships WHERE workspace_id=%s AND active "
                              "AND 'workspace_admin'=ANY(roles) ORDER BY user_id LIMIT 1", (workspace,)).fetchone()
        if existing:
            return existing[0]
        subject = "owned-controller-" + str(user)
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                   (user, fx.ISSUER, subject))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) "
                   "VALUES(%s,%s,%s,ARRAY['workspace_admin'],true,1) ON CONFLICT(workspace_id,user_id) DO NOTHING",
                   (uuid5(NAMESPACE_URL, subject), workspace, user))
        member = db.execute("SELECT active,roles FROM memberships WHERE workspace_id=%s AND user_id=%s",
                            (workspace, user)).fetchone()
        if not member or not member[0] or "workspace_admin" not in member[1]:
            raise ValueError("fixture controller was revoked; do not silently reactivate")
    return user


def approve_research_fixture(dsn, workspace, project, *, domains, search=None, model=None, actions=None,
                             transaction_role=False, countries=None, terms_overrides=None):
    from buyeros_api.api.policy_activation_schemas import ResearchProviderBinding
    owner = ensure_fixture_controller(dsn, workspace, project)
    scope = {"search": ResearchProviderBinding.model_validate(search).model_dump(mode="json") if search is not None else None,
             "model": ResearchProviderBinding.model_validate(model).model_dump(mode="json") if model is not None else None}
    selected = {"research.read", "research.persist", "research.fetch"}
    if search is not None:
        selected.add("research.search")
    if model is not None:
        selected.add("research.model")
    approve_native_fixture(dsn, workspace, project, owner, domains=domains,
        purposes=("account_research",), research_scope=scope,
        actions=sorted(selected if actions is None else actions), transaction_role=transaction_role, countries=countries,
        terms_overrides=terms_overrides)


def approve_selected_research_fixture(dsn, workspace, project, *, domains, countries=None, terms_overrides=None):
    from buyeros_api.providers import registry
    search = registry.DEFAULT_REGISTRY.registration("search")
    model = registry.DEFAULT_REGISTRY.registration("model")
    if search is not None and search.policy_binding is None:
        raise ValueError("fixture search account must be explicitly declared")
    if model is not None and model.policy_binding is None:
        raise ValueError("fixture model account must be explicitly declared")
    return approve_research_fixture(dsn, workspace, project, domains=domains,
        search=search.policy_binding if search is not None else None,
        model=model.policy_binding if model is not None else None, countries=countries,terms_overrides=terms_overrides)


def approve_page_license_fixture(dsn,workspace,project,url):
    """A new exact-source approval, never an UPDATE of approved history."""
    assert_owned_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        prior=db.execute("SELECT countries FROM policy_decisions WHERE workspace_id=%s AND subject_id=%s "
                         "AND purpose='account_research' ORDER BY version DESC,created_at DESC,id DESC LIMIT 1",
                         (workspace,project)).fetchone()
    approve_selected_research_fixture(dsn,workspace,project,domains=(urlsplit(url).hostname,),
        countries=prior[0] if prior else None,terms_overrides={
            "basis_reference":url,"provenance":"Owned fixture exact-source licensing review",
            "retention_days":1,"expires_at":(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()})
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT id,version FROM policy_decisions WHERE workspace_id=%s AND subject_id=%s "
                          "AND purpose='account_research' ORDER BY version DESC,created_at DESC,id DESC LIMIT 1",
                          (workspace,project)).fetchone()


@pytest.fixture
def policy_api(policy_case, monkeypatch):
    from fastapi.testclient import TestClient
    from buyeros_api.settings import get_settings
    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app
    from buyeros_api.api.jwks import JwksKeyCache
    from buyeros_api.api.verifier import TokenVerifier
    assert_owned_test_dsn(policy_case["dsn"])
    api_dsn = runtime_role_dsn(policy_case["dsn"])
    assert urlsplit(api_dsn).username == "buyeros_api"
    monkeypatch.setenv("BUYEROS_DATABASE_URL", api_dsn)
    monkeypatch.setenv("BUYEROS_AUTH_MODE", "auth0")
    monkeypatch.setenv("BUYEROS_" + "AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_" + "AUTH0_AUDIENCE", fx.AUDIENCE)
    monkeypatch.setenv("BUYEROS_PAID_ADMISSION_ENABLED", "false")
    monkeypatch.setenv("BUYEROS_DELIVERY_ADMISSION_ENABLED", "false")
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "false")
    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=300)
    monkeypatch.setattr(auth, "_verifier_from_settings",
                        lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))
    try:
        with TestClient(create_app(), raise_server_exceptions=True) as client:
            yield client
    finally:
        get_settings.cache_clear()


def policy_headers(case, role="requester", key=None):
    values = {"Authorization": "Bearer " + fx.make_token(sub=case["subjects"][role])}
    if key:
        values["Idempotency-Key"] = key
    return values
