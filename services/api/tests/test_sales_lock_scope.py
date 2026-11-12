"""Read routes take no workspace advisory gate; admission/mutation paths keep it.

The six observed 60s GET timeouts were caused by capability/native-source reads
holding ``pg_advisory_xact_lock`` policy+budget gates for the whole request while
the client also opened a second pooled connection for rate limiting. These tests
pin the repaired boundary without touching policy/budget enforcement itself:

* pure-read routes call ``access(..., locks=False)`` and acquire no gates;
* membership/role/rate-limit checks precede every gate;
* admission and mutation routes still call the default serialized ``access``;
* the live-read kill switch still fails before any session or lock.
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from buyeros_api.api.app import create_app
from buyeros_api.api.auth import get_principal
from buyeros_api.api.errors import ApiError
from buyeros_api.services import conversation_access as access_module
from buyeros_api.services import xverum_dispatch

WORKSPACE = uuid.uuid4()
PROJECT = uuid.uuid4()
ACTOR = uuid.uuid4()


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    """Only the project-existence probe is reached inside access()."""

    async def execute(self, statement):
        return _Result(SimpleNamespace(id=PROJECT))


def _fake_scope(monkeypatch, entered=None):
    @asynccontextmanager
    async def scope(workspace_id):
        if entered is not None:
            entered.append(workspace_id)
        yield _Session()

    monkeypatch.setattr(access_module, "tenant_scoped", scope)


def _fake_membership(monkeypatch, roles=("operator",), events=None):
    async def load(*args, **kwargs):
        if events is not None:
            events.append("membership")
        return {"user_id": ACTOR, "roles": list(roles)}

    monkeypatch.setattr(access_module, "load_membership", load)


def _spy_gates(monkeypatch, events=None):
    calls = []

    async def gates(session, workspace_id):
        calls.append(workspace_id)
        if events is not None:
            events.append("gates")

    monkeypatch.setattr(xverum_dispatch, "gates", gates)
    return calls


def _run(scenario):
    return asyncio.run(scenario())


def test_read_path_takes_no_policy_or_budget_advisory_lock(monkeypatch):
    events = []
    _fake_scope(monkeypatch)
    _fake_membership(monkeypatch, events=events)
    gates = _spy_gates(monkeypatch, events=events)

    async def scenario():
        async with access_module.access(
            WORKSPACE, PROJECT, object(), sales=True, admission=False, locks=False
        ) as (session, actor):
            assert isinstance(session, _Session)
            assert actor == ACTOR

    _run(scenario)
    assert gates == []
    assert events == ["membership"]


@pytest.mark.parametrize("kwargs", [{}, {"admission": False}])
def test_admission_and_mutation_paths_keep_the_workspace_gate(monkeypatch, kwargs):
    monkeypatch.setenv("BUYEROS_SALES_SKILLS_ENABLED", "true")
    monkeypatch.setenv("BUYEROS_SALES_WORKSPACE_IDS", str(WORKSPACE))
    events = []
    _fake_scope(monkeypatch)
    _fake_membership(monkeypatch, events=events)
    gates = _spy_gates(monkeypatch, events=events)

    async def scenario():
        async with access_module.access(
            WORKSPACE, PROJECT, object(), sales=True, **kwargs
        ):
            pass

    _run(scenario)
    assert gates == [WORKSPACE]
    assert events == ["membership", "gates"]


def test_default_preserves_serialized_behaviour_for_unreviewed_callers(monkeypatch):
    monkeypatch.setenv("BUYEROS_SALES_SKILLS_ENABLED", "true")
    monkeypatch.setenv("BUYEROS_SALES_WORKSPACE_IDS", str(WORKSPACE))
    _fake_scope(monkeypatch)
    _fake_membership(monkeypatch)
    gates = _spy_gates(monkeypatch)

    async def scenario():
        async with access_module.access(WORKSPACE, PROJECT, object(), sales=True):
            pass

    _run(scenario)
    assert gates == [WORKSPACE]


@pytest.mark.parametrize("roles", [(), ("policy_admin",)])
def test_unauthorised_read_fails_before_any_lock_acquisition(monkeypatch, roles):
    entered = []
    _fake_scope(monkeypatch, entered)
    _fake_membership(monkeypatch, roles=roles)
    gates = _spy_gates(monkeypatch)

    async def scenario():
        with pytest.raises(ApiError) as caught:
            async with access_module.access(
                WORKSPACE, PROJECT, object(), sales=True, admission=False, locks=False
            ):
                pytest.fail("denied read must not enter the session")
        assert caught.value.code == "NOT_FOUND"

    _run(scenario)
    assert gates == []


def test_membership_failure_fails_before_any_lock_acquisition(monkeypatch):
    _fake_scope(monkeypatch, entered := [])

    async def denied(*args, **kwargs):
        raise ApiError(404, "NOT_FOUND", "workspace not found")

    monkeypatch.setattr(access_module, "load_membership", denied)
    gates = _spy_gates(monkeypatch)

    async def scenario():
        with pytest.raises(ApiError):
            async with access_module.access(
                WORKSPACE, PROJECT, object(), sales=True, admission=False, locks=False
            ):
                pytest.fail("denied read must not enter the session")

    _run(scenario)
    assert gates == []


def test_live_read_kill_switch_still_fails_before_session_and_locks(monkeypatch):
    from buyeros_api.settings import get_settings

    entered = []
    _fake_scope(monkeypatch, entered)
    _fake_membership(monkeypatch)
    gates = _spy_gates(monkeypatch)
    monkeypatch.setenv("BUYEROS_LIVE_READ_ENABLED", "false")
    get_settings.cache_clear()
    try:
        async def scenario():
            with pytest.raises(ApiError) as caught:
                async with access_module.access(
                    WORKSPACE, PROJECT, object(), sales=True, admission=False, locks=False
                ):
                    pytest.fail("disabled live reads must not enter a session")
            assert caught.value.code == "READ_DISABLED"

        _run(scenario)
        assert entered == [] and gates == []
    finally:
        monkeypatch.delenv("BUYEROS_LIVE_READ_ENABLED", raising=False)
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Route wiring: read endpoints opt out; write endpoints keep the default gate.
# ---------------------------------------------------------------------------

ROOT = f"/v1/workspaces/{WORKSPACE}/projects/{PROJECT}"
SALES_ROOT = ROOT + "/sales-tasks"


def _client(monkeypatch, routes, observed):
    """Authenticated client whose ``access`` records call kwargs per route."""

    @asynccontextmanager
    async def fake_access(workspace_id, project_id, principal, **kwargs):
        observed.append(kwargs)
        yield object(), ACTOR

    monkeypatch.setattr(routes, "access", fake_access)
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


def _stub_sales_service(monkeypatch, routes):
    from buyeros_api.sales.contracts import TaskCollectionPage, TaskRecord

    record = TaskRecord(
        id=uuid.uuid4(), state="needs_input", revision=1,
        context_digest=None, output_ids=(), pending_review=None,
    )

    async def echo(*args, **kwargs):
        return record

    async def empty(*args, **kwargs):
        return []

    async def page(*args, **kwargs):
        return TaskCollectionPage(items=(), total=0, offset=0, limit=50)

    for name in ("create_task", "get_task", "cancel_task", "followup_task", "admit_step"):
        monkeypatch.setattr(routes.service, name, echo)
    from buyeros_api.execution import sales_tasks as execution

    async def empty_steps(*args, **kwargs):
        return []

    monkeypatch.setattr(execution, "list_steps", empty_steps)
    monkeypatch.setattr(routes.service, "read_events", empty)
    monkeypatch.setattr(routes.service, "list_tasks", page)


def _headers(version=1):
    return {
        "Authorization": "Bearer synthetic",
        "Idempotency-Key": "synthetic-lock-scope-key",
        "If-Match": f'"{version}"',
    }


TASK = {
    "thread_id": str(uuid.uuid4()),
    "skill_id": "sales-research",
    "skill_version": "1",
    "user_message": "Synthetic lock-scope request",
    "source_refs": [],
    "arguments": {"research_question": "Synthetic research"},
}


def test_route_wiring_reads_opt_out_and_writes_keep_the_lock(monkeypatch):
    from buyeros_api.api.routes import sales_tasks as routes

    monkeypatch.setenv("BUYEROS_SALES_SKILLS_ENABLED", "true")
    monkeypatch.setenv("BUYEROS_SALES_WORKSPACE_IDS", str(WORKSPACE))
    observed = []
    client = _client(monkeypatch, routes, observed)
    _stub_sales_service(monkeypatch, routes)
    task_path = SALES_ROOT + "/" + str(uuid.uuid4())

    reads = [
        client.get(SALES_ROOT + "/capability"),
        client.get(task_path),
        client.get(task_path + "/events"),
        client.get(SALES_ROOT + "?thread_id=" + str(uuid.uuid4())),
        client.get(task_path + "/steps"),
        client.get(ROOT + "/sales/skills"),
    ]
    for response in reads:
        assert response.status_code == 200, response.text
    assert observed and all(kwargs.get("locks") is False for kwargs in observed), observed

    observed.clear()
    writes = [
        client.post(SALES_ROOT, headers=_headers(), json=TASK),
        client.post(task_path + "/cancel", headers=_headers()),
        client.post(
            SALES_ROOT + "/" + str(uuid.uuid4()) + "/followups",
            headers=_headers(),
            json={"user_message": "add detail", "arguments": {"research_question": "Synthetic"}},
        ),
    ]
    for response in writes:
        assert response.status_code in {200, 201}, response.text
    assert observed and all("locks" not in kwargs for kwargs in observed), observed


def test_native_sources_uses_short_transactions_not_one_long_locked_read(monkeypatch):
    """TASK-4 residual: no transaction/lock may span the whole enumeration.

    The route must not run inside a read-only transaction (per-source validation
    uses write-capable retention helpers — CI caught a 25006 regression). It also
    must not hold the workspace gates across all candidates: candidate collection
    and each batch of at most 10 sources get their own short normal transaction.
    """
    from buyeros_api.api import deps as api_deps
    from buyeros_api.api.routes import sales_tasks as routes
    from buyeros_api.db import session as db_session
    from buyeros_api.sales import native_sources

    observed = []
    state = {'current': None, 'sessions': []}

    @asynccontextmanager
    async def fake_access(*args, **kwargs):
        observed.append(dict(kwargs))
        yield object(), ACTOR

    @asynccontextmanager
    async def fake_tenant_session(engine, workspace_id, *, read_only=False):
        marker = {'read_only': read_only, 'resolved': 0}
        state['sessions'].append(marker)
        state['current'] = marker

        class _Rows:
            def all(self):
                return [SimpleNamespace(id=uuid.uuid4(), version=1, number=1)]

        class _Session:
            async def scalars(self, statement):
                return _Rows()

        try:
            yield _Session()
        finally:
            state['current'] = None

    async def fake_resolve(*args, **kwargs):
        assert state['current'] is not None, 'resolution must happen inside a short transaction'
        state['current']['resolved'] += 1
        observed.append({'resolve_readonly': kwargs.get('readonly')})

    monkeypatch.setattr(routes, 'access', fake_access)
    monkeypatch.setattr(db_session, 'tenant_session', fake_tenant_session)
    monkeypatch.setattr(api_deps, 'get_engine', lambda: object())
    monkeypatch.setattr(native_sources, 'resolve_native_source', fake_resolve)
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(SALES_ROOT + '/native-sources')
    assert response.status_code == 200, response.text
    assert observed[0] == {'sales': True, 'admission': False, 'locks': False}
    # No read-only transaction anywhere: the path is legitimately write-capable.
    assert state['sessions'] and all(not marker['read_only'] for marker in state['sessions'])
    # Candidate collection plus at least one validation batch: more than one session.
    assert len(state['sessions']) >= 2
    # No single transaction spans the enumeration.
    assert all(marker['resolved'] <= 10 for marker in state['sessions'])
    assert sum(marker['resolved'] for marker in state['sessions']) == 3
    assert all(item.get('resolve_readonly') in (None, False)
        for item in observed if 'resolve_readonly' in item)
