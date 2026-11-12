"""Offline boundaries plus PostgreSQL HTTP acceptance (never mock ACL proof)."""
import uuid
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from buyeros_api.api.app import create_app
from tests.test_buyer_review_db import _seed_buyer, _h, OPERATOR, VIEWER, REVIEWER, ADMIN, WORKSPACE_A, PROJECT_A
from tests.test_conversation_threads_api import create as create_thread, grant, headers, member, ROOT as THREAD_ROOT

ROOT = f'/v1/workspaces/{uuid.uuid4()}/projects/{uuid.uuid4()}/sales-tasks'


@pytest.mark.parametrize('flag', [None, 'false', 'TRUE', 'true'])
def test_sales_disabled_without_workspace_opt_in(monkeypatch, flag):
    monkeypatch.delenv('BUYEROS_SALES_WORKSPACE_IDS', raising=False)
    if flag is None:
        monkeypatch.delenv('BUYEROS_SALES_SKILLS_ENABLED', raising=False)
    else:
        monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', flag)
    client = TestClient(create_app())
    for method, suffix in [('POST', ''), ('POST', '/')]:
        result = client.request(method, ROOT + suffix, json={'unknown': 'private'})
        assert result.status_code == 404
        assert result.headers['cache-control'] == 'no-store'
        assert result.headers['x-request-id'] == result.json()['request_id']
        assert result.json()['code'] == 'NOT_FOUND'


@pytest.mark.parametrize('flag', [None, 'false', 'TRUE', '1', 'true'])
@pytest.mark.parametrize('opted_in', [False, True])
@pytest.mark.parametrize('obsolete', ['false', 'true'])
def test_review_r1_exact_admission_flag(monkeypatch, flag, opted_in, obsolete):
    from buyeros_api.services.conversation_access import sales_enabled
    monkeypatch.setenv('BUYEROS_SALES_ENABLED', obsolete)
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS', WORKSPACE_A if opted_in else '')
    if flag is None:
        monkeypatch.delenv('BUYEROS_SALES_SKILLS_ENABLED', raising=False)
    else:
        monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', flag)
    assert sales_enabled(WORKSPACE_A) is (flag == 'true' and opted_in)


def test_review_r2_offline_admission_and_recovery_routes(monkeypatch):
    """Transport/access wiring only; real ACL recovery is covered by PostgreSQL below."""
    from contextlib import asynccontextmanager
    from buyeros_api.api.routes import sales_tasks as routes
    from buyeros_api.api.auth import get_principal
    from buyeros_api.sales.contracts import TaskRecord
    calls = []
    @asynccontextmanager
    async def access(*args, **kwargs):
        calls.append(kwargs)
        yield object(), uuid.uuid4()
    async def task(*args):
        return TaskRecord(id=uuid.uuid4(),state='needs_input',revision=1,context_digest=None,output_ids=(),pending_review=None)
    async def events(*args):
        return []
    monkeypatch.setattr(routes,'access',access)
    monkeypatch.setattr(routes.service,'create_task',task)
    monkeypatch.setattr(routes.service,'get_task',task)
    monkeypatch.setattr(routes.service,'cancel_task',task)
    monkeypatch.setattr(routes.service,'read_events',events)
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',WORKSPACE_A)
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    client = TestClient(app)
    assert client.post(SALES_ROOT,headers=headers(),json=task_body({'id':str(uuid.uuid4())})).status_code == 201
    assert calls[-1] == {'sales':True}
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    monkeypatch.delenv('BUYEROS_SALES_WORKSPACE_IDS')
    monkeypatch.delenv('NEXT_PUBLIC_CONVERSATION_HOME',raising=False)
    before = len(calls)
    assert client.post(SALES_ROOT, json={'invalid':'private'}).status_code == 404
    assert len(calls) == before
    path = SALES_ROOT+'/'+str(uuid.uuid4())
    for method, suffix in [('GET',''), ('GET','/events'), ('POST','/cancel')]:
        response = client.request(method,path+suffix,headers=headers())
        assert response.status_code == 200
        expected = {'sales':True,'admission':False}
        if method == 'GET':
            expected['locks'] = False  # pure reads do not serialize on workspace gates
        assert calls[-1] == expected
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-request-id'] == response.json()['request_id']


def test_review_r2_recovery_retains_live_read_control(monkeypatch):
    import asyncio
    from buyeros_api.services.conversation_access import access
    from buyeros_api.settings import get_settings
    from buyeros_api.api.errors import ApiError
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    monkeypatch.setenv('BUYEROS_LIVE_READ_ENABLED','false')
    get_settings.cache_clear()
    async def check():
        with pytest.raises(ApiError) as caught:
            async with access(uuid.UUID(WORKSPACE_A),uuid.UUID(PROJECT_A),object(),sales=True,admission=False):
                pytest.fail('live-read disabled must fail before database access')
        assert caught.value.code == 'READ_DISABLED'
    try:
        asyncio.run(check())
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize('state,expected', [('needs_input','cancelled'), ('queued','cancel_requested'), ('running','cancel_requested'), ('outcome_unknown','outcome_unknown'), ('cancel_requested','cancel_requested'), ('cancelled','cancelled'), ('completed','completed'), ('failed','failed')])
def test_cancel_does_not_claim_inflight_work_finished(state, expected):
    from buyeros_api.services.sales_tasks import cancellation_state
    assert cancellation_state(state) == expected


@pytest.mark.parametrize('state', ['queued','running','cancel_requested','outcome_unknown','partially_completed'])
def test_delete_refuses_unreconciled_work(state):
    from buyeros_api.services.sales_tasks import require_deletable
    from buyeros_api.api.errors import ApiError
    with pytest.raises(ApiError, match='cancel'):
        require_deletable([state])


def test_legacy_import_still_rejects_ai_bodies():
    from buyeros_api.api.routes.conversation_threads import ImportThread
    with pytest.raises(ValidationError):
        ImportThread(confirmed=True, template_id='custom', title='Synthetic', sources=[], messages=[{'text':'answer', 'kind':'ai'}])


def test_event_validation_rejects_content_and_kind_mismatch():
    from buyeros_api.services.sales_tasks import validated_event
    for kind, payload in [('progress', {'text':'private'}), ('error', {'state':'running','revision':1})]:
        with pytest.raises(ValidationError):
            validated_event(uuid.uuid4(), 1, kind, payload)


def test_preference_is_strict_and_actor_is_not_client_controlled():
    from buyeros_api.api.routes.conversation_threads import Preference
    assert Preference(pinned=True, archived=False).pinned is True
    for payload in [{'pinned':1,'archived':False}, {'pinned':True,'archived':False,'actor_id':str(uuid.uuid4())}]:
        with pytest.raises(ValidationError):
            Preference(**payload)


def test_offline_transport_matches_native_contract_and_errors(monkeypatch):
    """Transport-only stub; expressly not persistence or ACL evidence."""
    from contextlib import asynccontextmanager
    from buyeros_api.api.routes import sales_tasks as routes
    from buyeros_api.api.auth import get_principal
    from buyeros_api.sales.contracts import TaskRecord, TaskRecordResponse, EventPageResponse
    from buyeros_api.api.errors import ApiError
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',WORKSPACE_A)
    @asynccontextmanager
    async def access(*args, **kwargs):
        yield object(), uuid.uuid4()
    monkeypatch.setattr(routes, 'access', access)
    task_id = uuid.uuid4()
    async def get(*args):
        return TaskRecord(id=task_id,state='needs_input',revision=1,context_digest=None,output_ids=(),pending_review=None)
    async def events(*args):
        from buyeros_api.services.sales_tasks import validated_event
        return [validated_event(task_id, sequence, 'state', {'state':'needs_input','revision':1}) for sequence in (3,4)]
    monkeypatch.setattr(routes.service,'get_task',get)
    monkeypatch.setattr(routes.service,'read_events',events)
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    client = TestClient(app, raise_server_exceptions=False)
    path = f'{SALES_ROOT}/{task_id}'
    response = client.get(path)
    TaskRecordResponse.model_validate(response.json())
    EventPageResponse.model_validate(client.get(path+'/events?after=2').json())
    assert client.get(path+'/events?limit=101').status_code == 422
    assert client.get(path+'/events?limit=0').status_code == 422
    page = client.get(path+'/events?after=2&limit=1').json()['data']
    assert len(page['events']) == 1 and page['next_sequence'] == 3
    for header in (None, '1', 'W/"1"', '"0"'):
        h = {'Idempotency-Key':'synthetic-key'}
        if header is not None:
            h['If-Match'] = header
        result = client.post(path+'/cancel',headers=h)
        assert result.status_code == 400
    async def unavailable(*args):
        raise ApiError(503,'READ_DISABLED','temporarily unavailable')
    monkeypatch.setattr(routes.service,'get_task',unavailable)
    response = client.get(path)
    assert response.status_code == 503
    async def unexpected(*args):
        raise RuntimeError('private error body')
    monkeypatch.setattr(routes.service,'get_task',unexpected)
    response = client.get(path)
    assert response.status_code == 500 and 'private' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-request-id'] == response.json()['request_id']
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    monkeypatch.setattr(routes.service,'get_task',get)
    assert client.get(path).status_code == 200


def test_offline_task_input_rejects_oversized_and_nul_before_persistence():
    from buyeros_api.services.sales_tasks import validate_persisted_input
    from buyeros_api.sales.contracts import TaskInput
    from buyeros_api.api.errors import ApiError
    for body in [dict(user_message='hello\x00'), dict(arguments={'research_question':'x'*4000, 'language':'en'})]:
        value = {'thread_id':uuid.uuid4(),'skill_id':'sales-research','skill_version':'1','user_message':'Synthetic',
            'source_refs':[], 'arguments':{'research_question':'Synthetic'}}
        value.update(body)
        data = TaskInput(**value)
        if '\x00' in data.user_message:
            with pytest.raises(ApiError, match='NUL'):
                validate_persisted_input(data)
        else:
            validate_persisted_input(data)


def test_offline_sales_readiness_requires_exact_head_and_new_relations():
    from buyeros_api.services.schema_readiness import sales_requirements
    required = sales_requirements()
    assert required['compatible_heads'] == ['0072_turn_event_boundaries']
    assert required['required_revisions'] == ['0060_sales_tasks','0061_sales_outputs','0062_xverum_credits','0063_xverum_dispatch','0064_xverum_enrichment','0065_sales_lifecycle','0066_conversation_turns','0067_conversation_buyer','0068_conversation_turn_events','0069_turn_reconciliations','0070_turn_rate_windows','0071_conversation_retention','0072_turn_event_boundaries']
    assert set(required['required_relations']) == set(required['required_rls']) == {
        'public.sales_tasks','public.sales_task_events','public.sales_task_dependencies','public.conversation_thread_preferences',
        'public.conversation_threads','public.sales_reviews','public.sales_executions','public.sales_steps',
        'public.sales_outputs','public.sales_output_versions','public.sales_output_sections',
        'public.sales_output_dependencies','public.sales_output_native_links',
        'public.xverum_connections','public.xverum_project_assignments','public.xverum_credit_accounts',
        'public.xverum_credit_limits','public.xverum_tariffs','public.xverum_quotes',
        'public.xverum_credit_reservations','public.xverum_receipts','public.xverum_credit_settlements',
        'public.xverum_stages','public.xverum_tool_receipts','public.xverum_reconciliations','public.xverum_enrichments',
        'public.xverum_enrichment_dependencies',
        'public.sales_financial_evidence','public.sales_accounting_receipts','public.sales_content_tombstones',
        'public.conversation_thread_messages','public.conversation_turns','public.conversation_turn_proposals','public.conversation_turn_decisions','public.conversation_turn_events','public.conversation_turn_reconciliations','public.conversation_turn_rate_windows'}
    assert len(required['required_functions']) == 3


def test_offline_durable_message_identity_and_intent_bind_scope_payload_and_revision():
    from buyeros_api.services.sales_tasks import creation_identity
    from buyeros_api.sales.contracts import Scope, TaskInput
    scope = Scope(workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),actor_id=uuid.uuid4())
    data = TaskInput(thread_id=uuid.uuid4(),skill_id='sales-research',skill_version='1',user_message='Synthetic',
        source_refs=[],arguments={'research_question':'Synthetic'})
    identity, digest = creation_identity(scope,data,'synthetic-key',1)
    assert creation_identity(scope,data,'synthetic-key',1) == (identity,digest)
    assert creation_identity(scope,data.model_copy(update={'user_message':'changed'}),'synthetic-key',1)[0] == identity
    assert creation_identity(scope,data.model_copy(update={'user_message':'changed'}),'synthetic-key',1)[1] != digest
    assert creation_identity(scope,data,'synthetic-key',2)[1] != digest
    assert creation_identity(scope.model_copy(update={'project_id':uuid.uuid4()}),data,'synthetic-key',1)[1] != digest
    assert creation_identity(scope.model_copy(update={'actor_id':uuid.uuid4()}),data,'synthetic-key',1)[0] != identity


def test_offline_note_limit_errors_are_actionable_and_content_free(monkeypatch):
    from buyeros_api.api.auth import get_principal
    from tests.test_conversation_threads_api import BODY
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: object()
    client = TestClient(app)
    result = client.post(THREAD_ROOT+'/'+str(uuid.uuid4())+'/messages', json={'text':'PRIVATE'*700})
    assert result.status_code == 422 and '4,000' in result.json()['message']
    assert 'PRIVATE' not in result.text
    result = client.post(THREAD_ROOT,json={**BODY,'messages':[{'text':'PRIVATE'}]*101})
    assert result.status_code == 422 and '100' in result.json()['message']
    assert 'PRIVATE' not in result.text


@pytest.fixture
def sales_api(monkeypatch, request):
    # isolated_api allocates its own cluster/clone, never inherited DSNs.
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS', WORKSPACE_A)
    client = request.getfixturevalue('isolated_api')
    dsn = request.getfixturevalue('isolated_seeded')
    yield client, dsn
    # Reconcile only synthetic test tasks before fixture teardown, including failed assertions.
    import psycopg
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='cancelled'")
        db.execute('DELETE FROM conversation_threads')


SALES_ROOT = f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/sales-tasks'


def task_body(thread):
    return {'thread_id':thread['id'], 'skill_id':'sales-research', 'skill_version':'1',
        'user_message':'SYNTHETIC_TASK_NOTE', 'source_refs':[], 'arguments':{'research_question':'Synthetic research'}}


def create_task_http(client, thread, actor=OPERATOR, key='synthetic-task-key'):
    result = client.post(SALES_ROOT, headers=headers(actor, thread['version'], key), json=task_body(thread))
    assert result.status_code == 201, result.text
    return result.json()['data']


def test_postgres_task_identity_replay_conflict_and_cancel(sales_api):
    client, dsn = sales_api
    thread = create_thread(client)
    first = create_task_http(client, thread)
    replay = create_task_http(client, thread)
    assert replay['id'] == first['id']
    changed = {**task_body(thread), 'user_message':'different'}
    conflict = client.post(SALES_ROOT, headers=headers(key='synthetic-task-key'), json=changed)
    assert conflict.status_code == 409 and conflict.json()['code'] == 'IDEMPOTENCY_CONFLICT'
    stale = client.post(SALES_ROOT, headers=headers(key='different-task-key'), json=task_body(thread))
    assert stale.status_code == 409 and stale.json()['code'] == 'STALE_REVISION'
    path = SALES_ROOT + '/' + first['id']
    events = client.get(path+'/events?after=0', headers=_h()).json()['data']
    assert [event['sequence'] for event in events['events']] == [1]
    assert events['next_sequence'] == 1
    assert client.get(path+'/events?after=1', headers=_h()).json()['data']['events'] == []
    h = headers(key='cancel-task-key')
    cancelled = client.post(path+'/cancel', headers=h)
    assert cancelled.status_code == 200 and cancelled.json()['data']['state'] == 'cancelled'
    assert client.post(path+'/cancel', headers=h).json()['data'] == cancelled.json()['data']
    import psycopg
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM conversation_thread_messages').fetchone()[0] == 1
        assert db.execute('SELECT message_sequence FROM sales_tasks').fetchone()[0] == 1
        assert all(row[0] is None for row in db.execute("SELECT response FROM idempotency_records WHERE operation_id IN ('createSalesTask','cancelSalesTask')"))


def test_postgres_message_dedup_survives_receipt_expiry(sales_api):
    import psycopg
    client, dsn = sales_api
    thread = create_thread(client)
    first = create_task_http(client,thread)
    with psycopg.connect(dsn) as db:
        db.execute("DELETE FROM idempotency_records WHERE operation_id='createSalesTask'")
    replay = create_task_http(client,thread)
    assert replay['id'] == first['id']
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_tasks').fetchone()[0] == 1


def test_task_replay_after_share_revocation(sales_api):
    client, dsn = sales_api
    thread = grant(client, dsn, create_thread(client), REVIEWER, 'editor')
    first = create_task_http(client, thread, REVIEWER)
    path = SALES_ROOT + '/' + first['id']
    assert client.get(path, headers=_h(REVIEWER)).status_code == 200
    revoked = client.delete(f"{THREAD_ROOT}/{thread['id']}/shares/{member(dsn,REVIEWER)}", headers=headers(version=thread['version']+1))
    assert revoked.status_code == 200
    replay = client.post(SALES_ROOT, headers=headers(REVIEWER,thread['version'],'synthetic-task-key'), json=task_body(thread))
    assert replay.status_code == 404
    for suffix in ['', '/events?after=0']:
        assert client.get(path+suffix, headers=_h(REVIEWER)).status_code == 404
    assert client.post(path+'/cancel', headers=headers(REVIEWER)).status_code == 404
    import psycopg
    with psycopg.connect(dsn) as db:
        task_count = db.execute('SELECT count(*) FROM sales_tasks').fetchone()[0]
        assert task_count == 1


@pytest.mark.parametrize('actor,role', [(OPERATOR,'owner'), (REVIEWER,'editor'), (VIEWER,'viewer'), (ADMIN,None)])
def test_postgres_task_acl_matrix(sales_api, actor, role):
    client, dsn = sales_api
    thread = grant(client, dsn, create_thread(client), REVIEWER, 'editor')
    thread = grant(client, dsn, thread, VIEWER, 'viewer')
    task = create_task_http(client, thread)
    path = SALES_ROOT+'/'+task['id']
    for suffix in ['', '/events']:
        assert client.get(path+suffix, headers=_h(actor)).status_code == (200 if role else 404)
    assert client.post(path+'/cancel', headers=headers(actor)).status_code == (200 if role in {'owner','editor'} else 404)


@pytest.mark.parametrize('precondition', [None, '1', 'W/"1"', '"0"', '*'])
def test_postgres_task_requires_native_strong_preconditions(sales_api, precondition):
    client, _ = sales_api
    thread = create_thread(client)
    h = headers()
    h.pop('If-Match')
    if precondition is not None:
        h['If-Match'] = precondition
    response = client.post(SALES_ROOT, headers=h, json=task_body(thread))
    assert response.status_code == 400
    assert response.json()['code'] == 'INVALID_REQUEST'
    assert response.headers['cache-control'] == 'no-store'


def test_postgres_preferences_search_do_not_leak_private_titles(sales_api):
    client, dsn = sales_api
    thread = create_thread(client, title='SECRET_TITLE')
    assert client.get(THREAD_ROOT+'?q=SECRET_TITLE', headers=_h(ADMIN)).json()['data']['total'] == 0
    thread = grant(client, dsn, thread, VIEWER, 'viewer')
    path = f"{THREAD_ROOT}/{thread['id']}/preferences"
    assert client.put(path, headers=_h(VIEWER), json={'pinned':True,'archived':True}).status_code == 200
    owned = client.get(THREAD_ROOT+'?q=SYNTHETIC_USER_NOTE', headers=_h()).json()['data']
    assert owned['total'] == 1 and owned['items'][0]['pinned'] is False
    shared = client.get(THREAD_ROOT+'?pinned=true&archived=true', headers=_h(VIEWER)).json()['data']
    assert shared['total'] == 1 and shared['items'][0]['archived'] is True
    assert client.get(THREAD_ROOT+'?q=%25', headers=_h()).json()['data']['total'] == 0
    assert client.delete(f"{THREAD_ROOT}/{thread['id']}/shares/{member(dsn,VIEWER)}", headers=headers(version=thread['version'])).status_code == 200
    assert client.get(THREAD_ROOT+'?pinned=true&q=SECRET_TITLE', headers=_h(VIEWER)).json()['data']['total'] == 0
    assert client.put(path, headers=_h(VIEWER), json={'pinned':False,'archived':False}).status_code == 404


def test_postgres_running_task_blocks_deletion_then_erases_content(sales_api):
    import psycopg
    client, dsn = sales_api
    thread = create_thread(client)
    task = create_task_http(client, thread)
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='running' WHERE id=%s", (task['id'],))
    path = f"{THREAD_ROOT}/{thread['id']}"
    rejected = client.delete(path, headers=headers(version=2))
    assert rejected.status_code == 409 and rejected.json()['code'] == 'TASK_ACTIVE'
    cancelled = client.post(SALES_ROOT+'/'+task['id']+'/cancel', headers=headers())
    assert cancelled.json()['data']['state'] == 'cancel_requested'
    assert client.delete(path, headers=headers(version=2)).status_code == 409
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='cancelled' WHERE id=%s", (task['id'],))
    assert client.delete(path, headers=headers(version=2)).status_code == 200
    assert client.get(SALES_ROOT+'/'+task['id'], headers=_h()).status_code == 404
    with psycopg.connect(dsn) as db:
        for table in ('sales_tasks','sales_task_events','sales_task_dependencies','conversation_thread_preferences','conversation_thread_messages'):
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0


def test_postgres_concurrent_create_deduplicates(sales_api):
    from concurrent.futures import ThreadPoolExecutor
    client, _ = sales_api
    thread = create_thread(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create_task_http(client, thread), range(2)))
    assert results[0]['id'] == results[1]['id']


def test_postgres_review_r2_disabled_entry_preserves_current_acl_recovery(sales_api, monkeypatch):
    from buyeros_api.settings import get_settings
    client, dsn = sales_api
    thread = grant(client,dsn,create_thread(client),REVIEWER,'editor')
    task = create_task_http(client,thread)
    path = SALES_ROOT+'/'+task['id']
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    monkeypatch.setenv('BUYEROS_SALES_ENABLED','true')  # Obsolete variable cannot reopen admission.
    monkeypatch.delenv('BUYEROS_SALES_WORKSPACE_IDS')
    assert client.post(SALES_ROOT,headers=headers(),json=task_body(thread)).status_code == 404
    for subject in (OPERATOR,REVIEWER):
        for suffix in ('','/events?after=0'):
            assert client.get(path+suffix,headers=_h(subject)).status_code == 200
    revoked = client.delete(f"{THREAD_ROOT}/{thread['id']}/shares/{member(dsn,REVIEWER)}",
        headers=headers(version=thread['version']+1))
    assert revoked.status_code == 200
    for suffix in ('','/events?after=0'):
        assert client.get(path+suffix,headers=_h(REVIEWER)).status_code == 404
        assert client.get(path+suffix,headers=_h(ADMIN)).status_code == 404
    assert client.post(path+'/cancel',headers=headers(REVIEWER)).status_code == 404
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','false')
    assert client.get(path,headers=_h()).status_code == 200
    assert client.get(path+'/events',headers=_h()).status_code == 200
    cancelled = client.post(path+'/cancel',headers=headers())
    assert cancelled.status_code == 200 and cancelled.json()['data']['state'] == 'cancelled'
    monkeypatch.setenv('BUYEROS_LIVE_READ_ENABLED','false')
    get_settings.cache_clear()
    try:
        for method,suffix in [('GET',''),('GET','/events'),('POST','/cancel')]:
            result = client.request(method,path+suffix,headers=headers(version=2))
            assert result.status_code == 503 and result.json()['code'] == 'READ_DISABLED'
    finally:
        get_settings.cache_clear()


def test_postgres_native_sources_route_returns_200_for_candidate_rows(sales_api):
    """CI regression: per-source validation must not run in a read-only transaction.

    The route previously used a read-only tenant session around write-capable
    retention/native-read helpers, producing PostgreSQL 25006 and a 500 on
    GET /sales-tasks/native-sources. This asserts the real route against the real
    database, twice, and checks both sides of the documented filtering:

    * a candidate whose current authority/evidence validates (an approved profile
      with a reviewer-approved offer document excerpt) IS returned;
    * a bare canonical buyer with no current evidence is legitimately dropped by
      ``resolve_native_source`` (the route filtering is correct behaviour, not a
      bug to paper over).
    """
    import psycopg
    from psycopg.types.json import Jsonb
    from buyeros_api.db.icp import canonical_hash
    from tests.icp_fixtures import FACT_ID, valid_icp_payload

    client, dsn = sales_api
    profile = uuid.UUID('c5000000-0000-4000-8000-000000000001')
    document = uuid.UUID('c3000000-0000-4000-8000-000000000001')
    content = valid_icp_payload()
    content['offer_document_ids'] = [str(document)]
    fact = content['offer_facts'][0]
    fact.update(provenance='document_excerpt', source_document_id=str(document),
                excerpt='Approved source excerpt')
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,"
            "media_type,status,sha256,retention_until,fact_candidates) VALUES(%s,%s,%s,"
            "'upload','route.txt','text/plain','ready',%s,now()+interval '1 day',%s)",
            (document, WORKSPACE_A, PROJECT_A, 'a' * 64, Jsonb([fact])))
        conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,"
            "basis_offer_revision,content,content_hash,approved_by,approved_at) "
            "VALUES(%s,%s,%s,1,1,%s,%s,%s,now())",
            (profile, WORKSPACE_A, PROJECT_A, Jsonb(content), canonical_hash(content),
             uuid.uuid5(uuid.NAMESPACE_URL, ADMIN)))
        conn.execute('UPDATE projects SET active_icp_version_id=%s WHERE id=%s',
            (profile, PROJECT_A))
    buyer = _seed_buyer(dsn, name='Native Source Route')

    first = client.get(SALES_ROOT + '/native-sources', headers=_h())
    assert first.status_code == 200, first.text
    assert first.headers['cache-control'] == 'no-store'
    items = first.json()['data']['items']
    assert isinstance(items, list)
    # A fully authorised candidate is returned (proof the validation path ran).
    assert any(item['ref']['kind'] == 'profile' and item['ref']['id'] == str(profile)
        for item in items), items
    # Evidence-less buyers are excluded by resolve_native_source, by design.
    assert not any(item['ref']['id'] == str(buyer) for item in items), items
    # Repeat call: each request uses bounded short transactions only.
    second = client.get(SALES_ROOT + '/native-sources', headers=_h())
    assert second.status_code == 200, second.text
