"""Operator CLI: one-shot dispatch/sweep or a supervised rotating dispatcher."""

import argparse
import json
import uuid
import asyncio
import random
import sys
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from buyeros_api.db.worker import WorkerHeartbeat

from .app import celery_app
from .config import get_settings
from .dispatcher import dispatch_cycle, dispatch_once, sweep_once
from .engine import create_engine, run_async
from .tasks import publish_message


def _run(command: str, limit: int | None, owner: str) -> list[str]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    batch = limit if limit is not None else settings.batch_size

    async def body() -> list[str]:
        engine = create_engine()
        try:
            if command == "dispatch":
                return await dispatch_once(engine, publish_message, owner, now, batch, settings.lease_seconds)
            return await sweep_once(engine, publish_message, owner, now, batch, settings.lease_seconds)
        finally:
            await engine.dispose()

    return run_async(body())


def _broker_ready() -> None:
    with celery_app.connection() as connection:
        connection.ensure_connection(max_retries=1)


async def _heartbeat(engine, owner: str, state: str) -> None:
    at = datetime.now(timezone.utc)
    statement = insert(WorkerHeartbeat).values(
        worker_id=f"dispatcher:{owner}"[:128], observed_at=at, broker_state=state
    ).on_conflict_do_update(
        index_elements=[WorkerHeartbeat.worker_id],
        set_={"observed_at": at, "broker_state": state},
    )
    async with engine.begin() as connection:
        await connection.execute(statement)


def _run_loop(owner: str, max_total: int, time_budget_seconds: float, idle_seconds: float) -> None:
    if not 1 <= max_total <= 1000 or not 0 < time_budget_seconds <= 60 or not 0 < idle_seconds <= 60:
        raise ValueError("dispatcher loop requires bounded count and intervals")

    async def body() -> None:
        engine = create_engine()
        cursor = 0
        failures = 0
        try:
            while True:
                try:
                    await asyncio.to_thread(_broker_ready)
                    cycle = await dispatch_cycle(
                        engine, publish_message, owner, datetime.now(timezone.utc),
                        max_total=max_total, time_budget_seconds=time_budget_seconds,
                        cursor=cursor, lease_seconds=get_settings().lease_seconds,
                    )
                    cursor = cycle["next_cursor"]
                    await _heartbeat(engine, owner, "ready")
                    failures = 0
                    print(f"dispatch: published {len(cycle['published'])} intents", flush=True)
                    await asyncio.sleep(idle_seconds)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    failures += 1
                    print(f"dispatch: {type(error).__name__}; retrying", file=sys.stderr, flush=True)
                    try:
                        await _heartbeat(engine, owner, "unavailable")
                    except Exception:
                        pass
                    await asyncio.sleep(min(30.0, 2.0 ** min(failures, 5)) + random.uniform(0, 0.5))
        finally:
            await engine.dispose()

    run_async(body())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buyeros-worker", description="BuyerOS outbox dispatcher and recovery sweeper")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("dispatch", "claim and publish ready outbox intents"),
        ("sweep", "re-enqueue intents whose lease expired"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--limit", type=int, default=None, help="legacy one-shot max intents per workspace")
        command.add_argument("--owner", default=None, help="lease owner label")
        if name == "dispatch":
            command.add_argument("--loop", action="store_true", help="run the supervised dispatcher continuously")
            command.add_argument("--max-total", type=int, default=None, help="global intents per loop cycle")
            command.add_argument("--time-budget-seconds", type=float, default=10.0)
            command.add_argument("--idle-seconds", type=float, default=2.0)
    metrics = sub.add_parser("metrics", help="print tenant-scoped aggregate queue and hold metrics")
    metrics.add_argument("--workspace-id", required=True, type=uuid.UUID)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "metrics":
        from .metrics import collect_operational_metrics

        async def inspect():
            engine = create_engine()
            try:
                return await collect_operational_metrics(
                    engine, args.workspace_id, datetime.now(timezone.utc)
                )
            finally:
                await engine.dispose()
        print(json.dumps(run_async(inspect()), sort_keys=True))
        return 0
    owner = args.owner or f"buyeros-{args.command}"
    if args.command == "dispatch" and args.loop:
        try:
            _run_loop(owner, args.max_total or args.limit or get_settings().batch_size,
                      args.time_budget_seconds, args.idle_seconds)
        except KeyboardInterrupt:
            print("dispatch: stopped", flush=True)
        return 0
    published = _run(args.command, args.limit, owner)
    print(f"{args.command}: published {len(published)} intents")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
