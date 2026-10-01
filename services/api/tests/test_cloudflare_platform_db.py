"""Transport integration uses an owned cluster, loopback API and fictional identity.

No Auth0/provider/R2 credentials or database URLs are passed to Workers. Business
records below are explicit test fixtures, never live verification.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import psycopg
import uvicorn

from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_local_steps_db import seed_project
from tests.test_cloudflare_runtime_control_db import seed_envelope, worker_runtime


def test_actual_local_queue_workflow_api_postgres(migrated, worker_runtime, monkeypatch, tmp_path):
    from buyeros_api.api.app import create_app
    from buyeros_api.settings import get_settings

    envelope = seed_envelope(migrated, worker_runtime[1])
    project, actor, member = seed_project(migrated, envelope.workspace_id)
    job, company, buyer = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) "
                   "VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'queued',1)",
                   (job, envelope.workspace_id, project, actor, json.dumps({'owner_membership_id': str(member), 'reason': 'Fictional platform proof'})))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')", (company, envelope.workspace_id))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)", (buyer, envelope.workspace_id, project, company))
        db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,0,1,'pending')",
                   (uuid.uuid4(), envelope.workspace_id, job, buyer))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'job_id': str(job)}), envelope.outbox_id))
    monkeypatch.setenv('BUYEROS_WORKER_CURRENT_KEY_ID', 'fictional-key')
    monkeypatch.setenv('BUYEROS_WORKER_CURRENT_SECRET', 'fictional-cf05-secret-32-bytes-only')
    get_settings.cache_clear()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level='error', access_log=False))
    def serve():
        # Uvicorn's run() selects Proactor on Windows; psycopg requires Selector.
        # This is local fixture startup, not a runtime policy change in the API.
        asyncio.run(server.serve(sockets=[sock]),
                    loop_factory=asyncio.SelectorEventLoop if sys.platform == 'win32' else None)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started, 'owned API must actually start'
        context = tmp_path / 'opaque-worker-context.json'
        context.write_text(json.dumps({'origin': f'http://127.0.0.1:{port}', 'job': envelope.model_dump(mode='json')}), encoding='utf8')
        root = Path(__file__).resolve().parents[3]
        env = {key: value for key, value in os.environ.items() if not key.startswith(('BUYEROS_', 'AUTH0_', 'R2_', 'VERCEL_', 'CLOUDFLARE_'))}
        env['BUYEROS_CF_TEST_CONTEXT'] = str(context)
        result = subprocess.run(['node', 'node_modules/vitest/vitest.mjs', 'run', '--config', 'services/cloudflare-jobs/vitest.pg.config.ts',
                                 '--reporter=default', '--reporter=junit', '--outputFile.junit=artifacts/cloudflare/CF-platform-pg.xml'],
                                cwd=root, env=env, capture_output=True, text=True, encoding='utf8', timeout=120)
        (root / 'artifacts/cloudflare/CF-platform-pg.txt').write_text(result.stdout + result.stderr, encoding='utf8')
        assert result.returncode == 0, result.stdout + result.stderr
        with psycopg.connect(migrated) as db:
            assert db.execute('SELECT status,processed,updated,conflicts FROM async_jobs WHERE id=%s', (job,)).fetchone() == ('completed', 1, 1, 0)
            assert db.execute('SELECT version,owner_user_id FROM project_buyers WHERE id=%s', (buyer,)).fetchone() == (2, actor)
            assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='buyer.owner_assigned'", (envelope.workspace_id,)).fetchone()[0] == 1
            assert db.execute('SELECT count(*) FROM worker_steps WHERE outbox_id=%s', (envelope.outbox_id,)).fetchone()[0] == 1
            assert db.execute("SELECT state FROM outbox_events WHERE id=%s", (envelope.outbox_id,)).fetchone()[0] == 'done'
            probe_epoch, probe_id, observed = db.execute('SELECT runtime_epoch,last_probe_id,last_probe_at FROM worker_runtime_probe').fetchone()
            assert probe_epoch == worker_runtime[1] and probe_id is not None
            from datetime import datetime, timezone
            assert 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 180
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive(), 'local API must stop before owned DB teardown'
        get_settings.cache_clear()
