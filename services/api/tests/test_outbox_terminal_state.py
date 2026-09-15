"""Terminal outbox states and the dispatcher claim index (0007)."""

from pathlib import Path

from buyeros_api.db.outbox import OUTBOX_STATES, TERMINAL_STATES, OutboxEvent

MIGRATION = Path("alembic/versions/0007_outbox_terminal_state.py")


def test_terminal_states_are_done_and_failed():
    assert TERMINAL_STATES == frozenset({"done", "failed"})


def test_known_states_are_enumerated():
    assert OUTBOX_STATES == ("ready", "dispatched", "done", "failed")


def test_terminal_states_are_not_dispatchable():
    assert TERMINAL_STATES.isdisjoint({"ready", "dispatched"})


def test_model_enforces_the_state_set():
    checks = {
        constraint.name
        for constraint in OutboxEvent.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_outbox_events_state" in checks


def test_migration_revision_chains_from_0006():
    src = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "0007_outbox_terminal_state"' in src
    assert 'down_revision: str | None = "0006_worker_leases"' in src


def test_migration_names_the_state_constraint_and_index_explicitly():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "ck_outbox_events_state" in src
    assert "ix_outbox_events_state_lease_expires_at" in src
    assert "'done'" in src and "'failed'" in src


def test_migration_grants_workspaces_read_for_dispatch():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "GRANT SELECT ON workspaces TO buyeros_api, buyeros_worker;" in src
