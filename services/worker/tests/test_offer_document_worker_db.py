"""T16 private document parse and deletion across the worker boundary."""
import hashlib
import uuid

import psycopg

from buyeros_worker.tasks import execute_intent_sync
from tests.conftest import PROJECT_A, WS_A, reset_tenant, seed_outbox
from tests.test_pdf_parser import _pdf


def test_text_parse_is_durable_unapproved_and_delete_erases_private_object(
    worker_database_url, pg_dsn,
):
    body = b"Product: Sensor\nValue proposition: Better monitoring\n"
    digest = hashlib.sha256(body).hexdigest()
    document_id = str(uuid.uuid4())
    key = f"tenants/{WS_A}/{uuid.uuid4()}"
    parse_intent = f"offer.parse:{document_id}"
    delete_intent = f"offer.delete:{document_id}"
    objects = {key: body}

    class Store:
        async def get_private(self, object_key):
            assert object_key == key
            # The object I/O must not hold a row lock or transaction open.
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                conn.execute("SELECT id FROM offer_documents WHERE id=%s FOR UPDATE NOWAIT", (document_id,))
            return objects[object_key]

        async def delete_private(self, object_key):
            assert object_key == key
            objects.pop(object_key, None)

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("DELETE FROM offer_documents WHERE workspace_id=%s", (WS_A,))
        conn.execute(
            "INSERT INTO offer_documents(id, workspace_id, project_id, kind, filename,"
            " media_type, sha256, status, version, object_key)"
            " VALUES (%s,%s,%s,'upload','offer.txt','text/plain',%s,'quarantined',1,%s)",
            (document_id, WS_A, PROJECT_A, digest, key),
        )
        seed_outbox(conn, intent_key=parse_intent, event_type="offer.parse",
                    payload={"document_id": document_id}, state="dispatched", generation=1)
    assert execute_intent_sync(parse_intent, WS_A, 1, private_store=Store()) == "done"
    with psycopg.connect(pg_dsn) as conn:
        status, facts = conn.execute(
            "SELECT status, fact_candidates FROM offer_documents WHERE id=%s",
            (document_id,),
        ).fetchone()
        assert status == "ready"
        assert len(facts) == 2
        assert all(f["approved"] is False and f["source_document_id"] == document_id for f in facts)
    assert execute_intent_sync(parse_intent, WS_A, 1, private_store=Store()) == "duplicate"

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "UPDATE offer_documents SET status='deleted',fact_candidates='[]'::jsonb,"
            " deleted_at=now(),version=version+1 WHERE id=%s", (document_id,),
        )
        seed_outbox(conn, intent_key=delete_intent, event_type="offer.delete",
                    payload={"document_id": document_id}, state="dispatched", generation=1)
    assert execute_intent_sync(delete_intent, WS_A, 1, private_store=Store()) == "done"
    assert objects == {}
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert conn.execute(
            "SELECT object_key FROM offer_documents WHERE id=%s", (document_id,),
        ).fetchone()[0] is None
        conn.execute("DELETE FROM outbox_events WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM offer_documents WHERE id=%s", (document_id,))



def test_pdf_parse_persists_only_unapproved_extracted_facts(worker_database_url, pg_dsn):
    body = _pdf("Product: Sensor")
    digest = hashlib.sha256(body).hexdigest()
    document_id = str(uuid.uuid4())
    key = f"tenants/{WS_A}/{uuid.uuid4()}"
    intent = f"offer.parse:{document_id}"

    class Store:
        async def get_private(self, object_key):
            assert object_key == key
            return body

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("DELETE FROM offer_documents WHERE workspace_id=%s", (WS_A,))
        conn.execute(
            "INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,"
            "sha256,status,version,object_key) VALUES "
            "(%s,%s,%s,'upload','offer.pdf','application/pdf',%s,'quarantined',1,%s)",
            (document_id, WS_A, PROJECT_A, digest, key),
        )
        seed_outbox(conn, intent_key=intent, event_type="offer.parse",
                    payload={"document_id": document_id}, state="dispatched", generation=1)
    assert execute_intent_sync(intent, WS_A, 1, private_store=Store()) == "done"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        status, facts = conn.execute(
            "SELECT status,fact_candidates FROM offer_documents WHERE id=%s", (document_id,),
        ).fetchone()
        assert status == "ready"
        assert [(f["field"], f["value"], f["approved"]) for f in facts] == [
            ("product", "Sensor", False),
        ]
        conn.execute("DELETE FROM outbox_events WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM offer_documents WHERE id=%s", (document_id,))


def test_permitted_offer_url_fetch_persists_only_after_real_fixture_retrieval(
    worker_database_url, pg_dsn,
):
    import json
    from tests.conftest import WS_A

    source_url = "https://example.com/offer"
    actor_id = str(uuid.uuid4())
    document_id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
    intent = f"offer.fetch:{job_id}"
    objects = {}
    class Store:
        async def put_private(self, body, *, digest, retention_seconds):
            key = f"tenants/{WS_A}/{uuid.uuid4()}"
            objects[key] = body
            return key
        async def delete_private(self, key):
            objects.pop(key, None)
    class Transport:
        pinned_connections = True
        calls = []
        async def resolve(self, host):
            return ["93.184.216.34"]
        async def get(self, url, *, pinned_ip, timeout_seconds, max_transfer_bytes):
            self.calls.append((url, pinned_ip))
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                conn.execute("SELECT id FROM offer_documents WHERE id=%s FOR UPDATE NOWAIT", (document_id,))
                if getattr(self, "revoke", False):
                    conn.execute("UPDATE memberships SET roles='{viewer}' WHERE user_id=%s", (actor_id,))
            return 200, {"content-type": "text/html"}, b"<h1>Product: Sensor</h1><script>secret</script>"
    transport = Transport()
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("DELETE FROM offer_documents WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM async_jobs WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM policy_decisions WHERE workspace_id=%s", (WS_A,))
        conn.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'fixture','offer-fetch')", (actor_id,))
        conn.execute(
            "INSERT INTO memberships(id,workspace_id,user_id,roles,active)"
            " VALUES (%s,%s,%s,'{operator}',true)",
            (str(uuid.uuid4()), WS_A, actor_id),
        )
        conn.execute(
            "INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,version,source_url,retention_until)"
            " VALUES (%s,%s,%s,'url','pending-url-fetch','application/octet-stream','queued',1,%s,now()+interval '1 day')",
            (document_id, WS_A, PROJECT_A, source_url),
        )
        conn.execute(
            "INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested)"
            " VALUES (%s,%s,%s,%s,'offer_ingestion','ingestOfferUrl',%s::jsonb,'queued',1)",
            (job_id, WS_A, PROJECT_A, actor_id, json.dumps({"document_id": document_id, "source_url": source_url})),
        )
        seed_outbox(conn, intent_key=intent, event_type="offer.fetch",
                    payload={"document_id": document_id, "job_id": job_id},
                    state="dispatched", generation=1)
    assert execute_intent_sync(intent, WS_A, 1, private_store=Store(), fetch_transport=transport) == "policy_blocked"
    assert transport.calls == []
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO policy_decisions"
            "(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
            "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id)"
            " VALUES (%s,%s,'project',%s,%s,'offer_research','permitted',"
            "'fixture-reviewed',%s,'fixture-only','{HK}',now()+interval '1 day',1,%s)",
            (str(uuid.uuid4()), WS_A, PROJECT_A, WS_A, source_url, actor_id),
        )
    assert execute_intent_sync(intent, WS_A, 1, private_store=Store(), fetch_transport=transport) == "done"
    assert transport.calls == [(source_url, "93.184.216.34")]
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        status, digest, key = conn.execute(
            "SELECT status,sha256,object_key FROM offer_documents WHERE id=%s", (document_id,)
        ).fetchone()
        assert status == "ready" and len(digest) == 64 and key in objects
        assert b"Product: Sensor" in objects[key] and b"secret" not in objects[key]
        assert conn.execute("SELECT status FROM async_jobs WHERE id=%s", (job_id,)).fetchone()[0] == "completed"
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (intent,)).fetchone()[0] == "done"
        source = conn.execute(
            "SELECT canonical_url,digest,retrieved_at,language,object_key,excerpt,retention_until "
            "FROM source_documents WHERE id=%s AND workspace_id=%s", (document_id, WS_A),
        ).fetchone()
        assert source is not None
        assert source[0] == source_url and source[1] == hashlib.sha256(
            b"<h1>Product: Sensor</h1><script>secret</script>"
        ).hexdigest()
        assert source[2] is not None and source[3] == "und"
        assert source[4] == key and "secret" not in source[5] and source[6] is not None
        conn.execute("UPDATE offer_documents SET status='deleted', deleted_at=now(), version=version+1 WHERE id=%s", (document_id,))
        delete_intent = f"offer.delete:{document_id}"
        seed_outbox(conn, intent_key=delete_intent, event_type="offer.delete",
                    payload={"document_id": document_id}, state="dispatched", generation=1)
    assert execute_intent_sync(delete_intent, WS_A, 1, private_store=Store()) == "done"
    assert not objects
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert conn.execute("SELECT object_key,excerpt FROM source_documents WHERE id=%s", (document_id,)).fetchone() == (None, None)
    revoked_document, revoked_job = str(uuid.uuid4()), str(uuid.uuid4())
    revoked_intent = f"offer.fetch:{revoked_job}"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,status,version,source_url,retention_until)"
            " VALUES (%s,%s,%s,'url','pending-url-fetch','application/octet-stream','queued',1,%s,now()+interval '1 day')",
            (revoked_document, WS_A, PROJECT_A, source_url),
        )
        conn.execute(
            "INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested)"
            " VALUES (%s,%s,%s,%s,'offer_ingestion','ingestOfferUrl',%s::jsonb,'queued',1)",
            (revoked_job, WS_A, PROJECT_A, actor_id,
             json.dumps({"document_id": revoked_document, "source_url": source_url})),
        )
        seed_outbox(conn, intent_key=revoked_intent, event_type="offer.fetch",
                    payload={"document_id": revoked_document, "job_id": revoked_job},
                    state="dispatched", generation=1)
    transport.revoke = True
    assert execute_intent_sync(revoked_intent, WS_A, 1, private_store=Store(), fetch_transport=transport) == "stale"
    assert not objects, "orphan from revoked fetch must be deleted"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert conn.execute("SELECT status FROM offer_documents WHERE id=%s", (revoked_document,)).fetchone()[0] == "queued"
        assert conn.execute("SELECT count(*) FROM source_documents WHERE id=%s", (revoked_document,)).fetchone()[0] == 0
        conn.execute("DELETE FROM source_documents WHERE id=%s", (document_id,))
        conn.execute("DELETE FROM outbox_events WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM async_jobs WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM offer_documents WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM policy_decisions WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM memberships WHERE user_id=%s", (actor_id,))
        conn.execute("DELETE FROM users WHERE id=%s", (actor_id,))
