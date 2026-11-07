"""Ephemeral CLI authentication for fresh runners; no token in process arguments."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


@contextmanager
def authenticated_command(argv):
    token=os.environ.get('VERCEL_TOKEN','')
    if not argv or argv[0]!='vercel' or not token:
        yield argv
        return
    # The pinned CLI checks saved credentials before loading VERCEL_TOKEN. Use an
    # isolated config instead of relying on a developer's saved login. The
    # private directory/file are removed even when the command fails or times out.
    with tempfile.TemporaryDirectory(prefix='buyeros-vercel-auth-') as directory:
        path=Path(directory)/'auth.json'
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
            json.dump({'token':token},handle)
        command=list(argv)
        index=command.index('--') if '--' in command else len(command)
        command[index:index]=['--global-config',directory]
        yield command
