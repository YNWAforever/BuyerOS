"""Pinned, tenant-scoped LangGraph saver backed by Alembic-owned tables."""

from contextlib import asynccontextmanager
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.postgres.base import MIGRATIONS
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


@asynccontextmanager
async def open_checkpoint_saver(dsn: str, workspace_id):
    """Open one scoped connection; never call the saver's runtime ``setup``.

    The worker role has DML only. A mismatched Alembic/saver schema fails
    before graph execution rather than silently creating or changing tables.
    """
    workspace = uuid.UUID(str(workspace_id))
    async with await psycopg.AsyncConnection.connect(
        dsn, autocommit=True, row_factory=dict_row,
    ) as connection:
        from buyeros_api.services.worker_execution import WORKER_ROLE_CATALOG_SQL
        role = await connection.execute(WORKER_ROLE_CATALOG_SQL)
        proof = await role.fetchone()
        if proof is None or not next(iter(proof.values())):
            raise RuntimeError("worker role catalog proof failed")
        await connection.execute("SET search_path TO buyeros_graph, public")
        await connection.execute("SELECT set_config('app.workspace_id', %s, false)",
                                 (str(workspace),))
        result = await connection.execute("SELECT max(v) AS version FROM checkpoint_migrations")
        row = await result.fetchone()
        if row is None or row["version"] != len(MIGRATIONS) - 1:
            raise RuntimeError("LangGraph checkpoint schema version is incompatible")
        serializer = JsonPlusSerializer(allowed_msgpack_modules=[])
        yield AsyncPostgresSaver(connection, serde=serializer)
