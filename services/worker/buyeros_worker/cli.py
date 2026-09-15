"""Operator CLI for the dispatcher and sweeper roles.

    buyeros-worker dispatch [--limit N] [--owner NAME]
    buyeros-worker sweep    [--limit N] [--owner NAME]

Both commands run once and exit; the worker process serves the broker, and
Celery beat schedules the sweeper (``buyeros.sweep``). No deployment is implied.
"""

import argparse
import asyncio
from datetime import datetime, timezone

from .config import get_settings
from .dispatcher import dispatch_once, sweep_once
from .engine import create_engine
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

    return asyncio.run(body())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buyeros-worker", description="BuyerOS outbox dispatcher and recovery sweeper")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("dispatch", "claim and publish ready outbox intents"),
        ("sweep", "re-enqueue intents whose lease expired"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--limit", type=int, default=None, help="max intents per workspace")
        command.add_argument("--owner", default=None, help="lease owner label")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    owner = args.owner or f"buyeros-{args.command}"
    published = _run(args.command, args.limit, owner)
    print(f"{args.command}: published {len(published)} intents")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
