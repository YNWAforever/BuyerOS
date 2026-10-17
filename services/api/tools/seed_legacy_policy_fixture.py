"""Controlled approvals for the two explicitly fictional legacy browser projects."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID
import psycopg
import os
from functools import lru_cache

from tests.policy_activation_target import assert_owned_test_dsn
from tests import policy_activation_fixtures as helpers
from buyeros_api.api.policy_activation_schemas import MANUAL_ACTIONS
from buyeros_api.db.icp import canonical_hash
from buyeros_api.services import policy_activation_bootstrap as bootstrap

WORKSPACE = UUID("e0000000-0000-4000-8000-000000000001")
PROJECTS = (UUID("e1000000-0000-4000-8000-000000000001"),
            UUID("e9100000-0000-4000-8000-000000000001"))
SEARCH_BINDING = {"provider_name": "fixture", "account_reference": "owned-research-account",
                  "contract_sha256": canonical_hash({"schema": "owned-research-fixture.v1",
                    "service": "search", "provider": "fixture"}).removeprefix("sha256:")}


def seed_legacy_policy_fixture(dsn):
    assert_owned_test_dsn(dsn)
    with psycopg.connect(dsn) as db:
        if db.execute("SELECT name FROM workspaces WHERE id=%s", (WORKSPACE,)).fetchone() != ("E2E fixture workspace",):
            raise ValueError("fictional browser workspace required")
        projects = db.execute("SELECT id,active_sender_identity_version_id FROM projects "
                              "WHERE workspace_id=%s AND id=ANY(%s)", (WORKSPACE, list(PROJECTS))).fetchall()
    for project, sender in projects:
        owner = helpers.ensure_fixture_controller(dsn, WORKSPACE, project)
        with psycopg.connect(dsn) as db:
            membership = db.execute("SELECT version FROM memberships WHERE workspace_id=%s AND user_id=%s",
                                    (WORKSPACE, owner)).fetchone()[0]
            urls = db.execute("SELECT canonical_url FROM source_documents WHERE workspace_id=%s AND project_id=%s",
                              (WORKSPACE, project)).fetchall()
            contacts = [r[0] for r in db.execute("SELECT DISTINCT c.id FROM contact_points c JOIN project_buyers b "
                "ON b.workspace_id=c.workspace_id AND b.company_id=c.company_id WHERE b.workspace_id=%s "
                "AND b.project_id=%s AND c.validity='provider_marked_valid' AND NOT c.quarantined "
                "AND c.checked_at IS NOT NULL AND c.retention_expires_at>now()", (WORKSPACE, project)).fetchall()]
            company_domains = [r[0] for r in db.execute("SELECT DISTINCT c.domain FROM companies c JOIN project_buyers b "
                "ON b.workspace_id=c.workspace_id AND b.company_id=c.id JOIN evidence e "
                "ON e.workspace_id=b.workspace_id AND e.project_id=b.project_id AND e.company_id=c.id "
                "WHERE b.workspace_id=%s AND b.project_id=%s", (WORKSPACE, project)).fetchall() if r[0]]
        domains = sorted({"fixture.example.test", *company_domains, *(urlsplit(r[0]).hostname for r in urls)})
        quote_fixture = project == PROJECTS[0] and os.environ.get("BUYEROS_E2E_SEED_QUOTES") == "1"
        quote_actions = {"contact.enrich"} if quote_fixture else set()
        now = datetime.now(timezone.utc)
        case = {"dsn": dsn, "workspace": WORKSPACE, "project": project,
                "actors": {"owner": owner}, "membership_version": membership, "now": now}
        manifest = bootstrap.AuthorityManifest.model_validate({**helpers.manifest_body(case),
            "purposes": ["account_research", "contact_research", "draft_preparation", "outreach"],
            "allowed_actions": sorted(MANUAL_ACTIONS | {"research.search", "research.read", "research.persist",
                                      "research.fetch", "contact.read", "draft.generate", "delivery.review"} | quote_actions)})
        authorization = bootstrap.BootstrapAuthorization(manifest_sha256=bootstrap.manifest_digest(manifest),
            target_sha256=manifest.target_sha256, source_sha=manifest.source_sha,
            approval_reference="fixture://owned-legacy-browser-designation", approval_evidence_sha256="b"*64)
        async def designate(session):
            execution = await bootstrap.verify_bootstrap_execution(session, manifest, authorization)
            return await bootstrap.apply_authority_manifest(session, manifest, execution, now)
        helpers.owner_run(case, designate)
        helpers.approve_research_fixture(dsn, WORKSPACE, project, domains=domains,
            search=SEARCH_BINDING, transaction_role=True, countries=("US",))
        scope = {"provider_name": "fixture", "account_reference": "owned-browser-account",
                 "contract_sha256": canonical_hash({"schema": "owned-browser-template.v1"}).removeprefix("sha256:"),
                 "recipient_refs": [str(c) for c in contacts]}
        if contacts or quote_fixture:
            contact_scope = scope
            if quote_fixture:
                from buyeros_api.providers.registry import ProviderRegistration
                cap = browser_contact_capability()
                contact_scope = {**scope, "provider_name": cap.provider, "account_reference": "fixture-test",
                    "contract_sha256": ProviderRegistration(cap, lambda: None).contract_hash}
            helpers.approve_provider_fixture(dsn, WORKSPACE, project, owner, purpose="contact_research",
                domains=domains, actions=sorted(quote_actions | ({"contact.read"} if contacts else set())),
                scope=contact_scope, transaction_role=True)
        if sender:
            addressed = {**scope, "sender_identity_id": str(sender)}
            helpers.approve_provider_fixture(dsn, WORKSPACE, project, owner, purpose="draft_preparation",
                domains=domains, scope={**addressed, "allow_unaddressed_drafts": True}, transaction_role=True)
            if contacts:
                helpers.approve_provider_fixture(dsn, WORKSPACE, project, owner, purpose="outreach",
                    domains=domains, actions=["delivery.review"], scope=addressed, transaction_role=True)


@lru_cache(maxsize=1)
def browser_contact_capability():
    """One immutable fake contract shared by this fixture's quote and adapter.

    This caches contract metadata only. Approval/permission proofs stay fresh.
    """
    from decimal import Decimal
    from buyeros_api.providers.base import Money, ProviderCapability
    return ProviderCapability(provider="fixture", adapter_version="contact-fixture-v1", service="contact",
        markets=frozenset({"US"}), languages=frozenset({"en"}), roles=frozenset({"Procurement manager"}),
        auth_model="fixture", pricing_version="fixture-price-v1", max_liability=Money(Decimal("0.300000")),
        idempotency="verified", status="verified", callback="unsupported", cancel="unsupported",
        retention="fixture-only", verified_at=datetime.now(timezone.utc),
        source_urls=("https://fixture.invalid/capability",))
