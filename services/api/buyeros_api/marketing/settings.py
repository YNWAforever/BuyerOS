"""Deliberately separate from tenant settings; no default database or secret."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class MarketingSettings:
    database_url: str = field(repr=False)
    gateway_key: str = field(repr=False)
    public_origin: str
    synthetic: bool
    retention_days: int
    global_per_hour: int
    email_per_day: int
    challenges_per_minute: int


def enabled(value):
    return value in {"1", "true"}


def load_settings() -> MarketingSettings | None:
    """Fail closed on absent, malformed or unapproved real intake configuration."""
    env = os.environ
    if not enabled(env.get("BUYEROS_MARKETING_ENABLED")):
        return None
    synthetic = enabled(env.get("BUYEROS_MARKETING_SYNTHETIC_MODE"))
    if not synthetic and not enabled(env.get("BUYEROS_MARKETING_REAL_INTAKE_APPROVED")):
        return None
    dsn = env.get("BUYEROS_MARKETING_DATABASE_URL", "")
    key = env.get("BUYEROS_MARKETING_GATEWAY_KEY", "")
    origin = env.get("BUYEROS_MARKETING_PUBLIC_ORIGIN", "")
    try:
        database, public = urlsplit(dsn), urlsplit(origin)
        # Runtime role and dedicated DB/schema provisioning are separate explicit operations.
        if (database.scheme != "postgresql" or not database.hostname or not database.username
            or database.path in {"", "/"} or database.query or database.fragment
            or len(key) < 32 or not key.isascii()
            or public.scheme not in {"https", "http"} or not public.hostname
            or public.username or public.password or public.path or public.query or public.fragment
            or origin != f"{public.scheme}://{public.netloc}"
            or (public.scheme == "http" and public.hostname not in {"127.0.0.1", "localhost", "::1"})):
            return None
        retention = int(env["BUYEROS_MARKETING_RETENTION_DAYS"])
        global_limit = int(env.get("BUYEROS_MARKETING_GLOBAL_PER_HOUR", "20"))
        email_limit = int(env.get("BUYEROS_MARKETING_EMAIL_PER_DAY", "3"))
        challenge_limit = int(env.get("BUYEROS_MARKETING_CHALLENGES_PER_MINUTE", "100"))
        if not (1 <= retention <= 365 and 1 <= global_limit <= 10000
                and 1 <= email_limit <= 100 and 1 <= challenge_limit <= 10000):
            return None
    except (KeyError, ValueError):
        return None
    return MarketingSettings(dsn, key, origin, synthetic, retention, global_limit, email_limit, challenge_limit)
