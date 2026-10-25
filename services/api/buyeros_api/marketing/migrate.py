"""Independent migration. Invoke only with an explicitly approved intake owner connection.

Never included in the tenant Alembic chain and never invoked by an HTTP request.
Provision a dedicated database and restricted runtime login before enabling intake.
"""

DDL = """
CREATE SCHEMA IF NOT EXISTS marketing_intake;
REVOKE ALL ON SCHEMA marketing_intake FROM PUBLIC;
CREATE TABLE IF NOT EXISTS marketing_intake.schema_version (
    version integer PRIMARY KEY CHECK (version = 1)
);
INSERT INTO marketing_intake.schema_version VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS marketing_intake.challenges (
    id uuid PRIMARY KEY,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '15 minutes',
    consumed boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS challenges_issued ON marketing_intake.challenges (issued_at);
CREATE TABLE IF NOT EXISTS marketing_intake.leads (
    id uuid PRIMARY KEY,
    idempotency_key uuid NOT NULL UNIQUE,
    request_fingerprint text NOT NULL,
    name varchar(120) NOT NULL,
    email varchar(254) NOT NULL,
    company varchar(160) NOT NULL,
    message varchar(2000) NOT NULL,
    locale text NOT NULL CHECK (locale IN ('en', 'zh-HK')),
    synthetic boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS leads_created ON marketing_intake.leads (created_at);
CREATE INDEX IF NOT EXISTS leads_email_created ON marketing_intake.leads (email, created_at);
"""


def migrate(connection):
    connection.execute(DDL)
