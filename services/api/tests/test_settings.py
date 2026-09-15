import pytest

from buyeros_api.settings import Settings


def test_settings_defaults_are_fail_closed():
    s = Settings()
    assert s.auth0_issuer is None
    assert s.auth0_audience is None
    assert s.jwks_cache_seconds == 300
    assert s.environment == "local"


def test_settings_rejects_sqlite():
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///dev.db")


def test_settings_accepts_postgres():
    s = Settings(database_url="postgresql://u:p@localhost:5432/db")
    assert s.database_url.startswith("postgresql")
