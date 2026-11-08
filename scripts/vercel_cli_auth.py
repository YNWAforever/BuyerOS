"""Ephemeral CLI authentication for fresh runners; no token in process arguments."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


def curl_command(argv):
    """Select only protected curl's pinned CLI; never fall back to PATH's Vercel."""
    if list(argv[:2]) != ['vercel', 'curl']:
        return argv
    try:
        package = Path(os.environ.get('BUYEROS_VERCEL_CURL_PACKAGE', ''))
        if not package.is_absolute():
            raise ValueError
        package = package.resolve(strict=True)
        metadata = json.loads((package / 'package.json').read_text(encoding='utf-8'))
        entry = package / 'dist/vc.js'
        if (metadata.get('name') != 'vercel' or metadata.get('version') != '50.28.0'
                or metadata.get('bin', {}).get('vercel') != './dist/vc.js'
                or not entry.is_file() or entry.resolve().parent != package / 'dist'):
            raise ValueError
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError('protected curl CLI pin is invalid') from None
    return ['node', str(entry), *argv[1:]]


@contextmanager
def authenticated_command(argv):
    token=os.environ.get('VERCEL_TOKEN','')
    if not argv or argv[0]!='vercel' or not token:
        yield curl_command(argv)
        return
    # CLI 50.28 checks saved credentials before loading VERCEL_TOKEN. Use an
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
        yield curl_command(command)
