"""Guard: Alembic revision ids must fit ``alembic_version.version_num``.

Alembic creates ``alembic_version.version_num`` as ``VARCHAR(32)``. A revision id
longer than 32 characters makes every migration fail at start-up with
``StringDataRightTruncation`` ??an outage rather than a test failure ??so the
chain is inspected here without touching a database.

The filename may be longer than the id; only the internal ``revision`` value is
stored.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

SERVICE_ROOT = Path(__file__).resolve().parents[1]
MAX_LEN = 32


def scripts() -> ScriptDirectory:
    config = Config(str(SERVICE_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(SERVICE_ROOT / 'alembic'))
    return ScriptDirectory.from_config(config)


def test_every_revision_id_fits_the_version_column():
    too_long = sorted(
        (revision.revision, len(revision.revision))
        for revision in scripts().walk_revisions()
        if len(revision.revision) > MAX_LEN
    )
    assert not too_long, f'revision ids exceed {MAX_LEN} characters: {too_long}'


def test_the_chain_has_exactly_one_head_and_no_broken_links():
    chain = scripts()
    heads = list(chain.get_revisions('heads'))
    assert len(heads) == 1, f'expected one head, found {[head.revision for head in heads]}'
    bases = list(chain.get_bases())
    assert len(bases) == 1, f'expected one base, found {[base.revision for base in bases]}'
    ids = {revision.revision for revision in chain.walk_revisions()}
    dangling = [down for revision in chain.walk_revisions()
                for down in (revision.down_revision if isinstance(revision.down_revision, tuple)
                             else (revision.down_revision,) if revision.down_revision else ())
                if down not in ids]
    assert not dangling, f'down_revision not present in the chain: {dangling}'

import re as _re

INVALID_DDL = (
    # PostgreSQL has DISABLE ROW LEVEL SECURITY and NO FORCE ROW LEVEL SECURITY;
    # "NO ROW LEVEL SECURITY" is a syntax error that only shows up on downgrade.
    _re.compile(r'\bNO\s+ROW\s+LEVEL\s+SECURITY\b', _re.IGNORECASE),
    _re.compile(r'\bENABLE\s+ROW\s+LEVEL\s+SECURITY\s+DISABLE\b', _re.IGNORECASE),
)


def test_migrations_do_not_contain_invalid_row_security_ddl():
    offenders = {}
    for path in sorted((SERVICE_ROOT / 'alembic' / 'versions').glob('*.py')):
        text = path.read_text(encoding='utf-8')
        for pattern in INVALID_DDL:
            match = pattern.search(text)
            if match:
                offenders[path.name] = match.group(0)
    assert not offenders, f'invalid row-level-security DDL in migrations: {offenders}'

def test_owned_readback_fixture_pins_the_current_head():
    """The E2E readback fixture asserts the deployed schema head; keep it in sync."""
    fixture = SERVICE_ROOT.parents[1] / 'tests' / 'e2e' / 'fixtures' / 'c61-owned-readback.py'
    if not fixture.exists():
        return  # fixture only exists in the repository root, not in a packaged service
    text = fixture.read_text(encoding='utf-8')
    head = list(scripts().get_revisions('heads'))[0].revision
    pinned = _re.search(r"assert schema=='([^']+)'", text)
    assert pinned is not None, 'readback fixture no longer pins a schema head'
    assert pinned.group(1) == head, (
        f'readback fixture pins {pinned.group(1)} but the alembic head is {head}')
