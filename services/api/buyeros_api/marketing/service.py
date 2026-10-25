"""Small synchronous PostgreSQL store, isolated from all tenant models and engines."""
from uuid import uuid4

import psycopg

from .model import LeadInput
from .settings import MarketingSettings


class IntakeError(Exception):
    def __init__(self, code, status, retryable=False):
        self.code, self.status, self.retryable = code, status, retryable


def connect(settings):
    return psycopg.connect(settings.database_url, connect_timeout=3,
                           options="-c search_path=marketing_intake,pg_catalog -c statement_timeout=5000 -c lock_timeout=3000")


def begin(connection, settings):
    # Single transaction lock makes cross-process budgets + challenge use + replay atomic.
    # It is local to the separately configured intake database, never a tenant lock.
    connection.execute("SELECT pg_advisory_xact_lock(814729361)")
    role = connection.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
    if role != (False, False):
        raise IntakeError("intake_unavailable", 503, True)
    connection.execute("DELETE FROM marketing_intake.leads WHERE created_at < clock_timestamp() - %s * interval '1 day'", (settings.retention_days,))
    connection.execute("DELETE FROM marketing_intake.challenges WHERE expires_at < clock_timestamp()")


def issue_challenge(settings: MarketingSettings):
    challenge_id = str(uuid4())
    with connect(settings) as connection:
        begin(connection, settings)
        count = connection.execute("SELECT count(*) FROM marketing_intake.challenges WHERE issued_at >= clock_timestamp() - interval '1 minute'").fetchone()[0]
        if count >= settings.challenges_per_minute:
            raise IntakeError("rate_limited", 429, True)
        connection.execute("INSERT INTO marketing_intake.challenges (id) VALUES (%s)", (challenge_id,))
    return {"challenge_id": challenge_id}


def submit_lead(settings: MarketingSettings, lead: LeadInput, key: str):
    fingerprint = lead.fingerprint()
    with connect(settings) as connection:
        begin(connection, settings)
        saved = connection.execute("SELECT id::text, request_fingerprint, synthetic FROM marketing_intake.leads WHERE idempotency_key=%s", (key,)).fetchone()
        if saved:
            if saved[1] != fingerprint:
                raise IntakeError("idempotency_conflict", 409)
            receipt_id, synthetic, created = saved[0], saved[2], False
        else:
            challenge = connection.execute("SELECT consumed, issued_at <= clock_timestamp() - interval '2 seconds', expires_at > clock_timestamp() FROM marketing_intake.challenges WHERE id=%s FOR UPDATE", (lead.challenge_id,)).fetchone()
            if not challenge or challenge != (False, True, True):
                raise IntakeError("challenge_invalid", 422)
            global_count, email_count = connection.execute("SELECT count(*) FILTER (WHERE created_at >= clock_timestamp() - interval '1 hour'), count(*) FILTER (WHERE email=%s) FROM marketing_intake.leads WHERE created_at >= clock_timestamp() - interval '1 day'", (lead.email,)).fetchone()
            if global_count >= settings.global_per_hour or email_count >= settings.email_per_day:
                raise IntakeError("rate_limited", 429, True)
            receipt_id, synthetic, created = str(uuid4()), settings.synthetic, True
            connection.execute("INSERT INTO marketing_intake.leads (id,idempotency_key,request_fingerprint,name,email,company,message,locale,synthetic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (receipt_id, key, fingerprint, lead.name, lead.email, lead.company, lead.message, lead.locale, synthetic))
            connection.execute("UPDATE marketing_intake.challenges SET consumed=true WHERE id=%s", (lead.challenge_id,))
    # The context manager has committed successfully before an acknowledgment exists.
    return {"receipt_id": receipt_id, "status": "received", "synthetic": synthetic}, created
