"""Alembic environment (BO-005).

Alembic is the single owner of the BuyerOS domain schema. Migrations are run
with a dedicated migration-owner role; the API and worker roles are non-owner
and cannot mutate schema (see migration 0002).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from buyeros_api.db.models import Base
from buyeros_api.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    settings = get_settings()
    url = settings.database_migration_url or settings.database_url
    # Migrations use a synchronous psycopg (v3) driver.
    url = url.replace("+asyncpg", "+psycopg")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
