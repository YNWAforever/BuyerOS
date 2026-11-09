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
