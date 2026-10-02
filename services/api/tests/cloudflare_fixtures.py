"""Private owned clusters keep operational mutation tests out of public fixtures."""
import os

import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _start_container, _docker


@pytest.fixture(scope="module")
def cloudflare_database():
    from buyeros_api.settings import get_settings
    name, dsn = _start_container()
    old = {key: os.environ.get(key) for key in ("BUYEROS_DATABASE_URL", "BUYEROS_DATABASE_MIGRATION_URL")}
    try:
        os.environ["BUYEROS_DATABASE_URL"] = dsn
        os.environ.pop("BUYEROS_DATABASE_MIGRATION_URL", None)
        get_settings.cache_clear()
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
        command.upgrade(config, "head")
        yield dsn
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        _docker("rm", "-f", name)
