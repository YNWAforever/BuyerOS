"""Exercise a historical migration without erasing newer approval history."""
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import create_engine

from tests.policy_activation_target import assert_owned_test_dsn


def invoke_revision(dsn, config, revision, direction="downgrade", arguments=()):
    assert_owned_test_dsn(dsn)
    directory=ScriptDirectory.from_config(config)
    script = directory.get_revision(revision)
    engine = create_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        with engine.begin() as connection:
            with EnvironmentContext(config,directory,as_sql=False) as environment:
                environment.configure(connection=connection)
                with Operations.context(environment.get_context()):
                    getattr(script.module, direction)(*arguments)
    finally:
        engine.dispose()
