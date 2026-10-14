"""Parent boundary for credential-free, resource-capped PowerPoint parsing."""
import json
import subprocess
import sys
import tempfile

from .subprocess_runtime import child_environment

PARSER_TIMEOUT_SECONDS = 8


class PptxParserTimeout(ValueError):
    pass


def parse_pptx(body: bytes) -> dict:
    if not isinstance(body, bytes) or not body.startswith(b'PK\x03\x04') or not 0 < len(body) <= 20 * 1024 * 1024:
        raise ValueError('invalid PowerPoint bytes')
    with tempfile.TemporaryDirectory(prefix='buyeros-pptx-') as workdir:
        try:
            result = subprocess.run(
                [sys.executable, '-B', '-m', 'buyeros_api.execution.pptx_parser_child'],
                input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=PARSER_TIMEOUT_SECONDS, check=False, cwd=workdir, env=child_environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
        except subprocess.TimeoutExpired as exc:
            raise PptxParserTimeout('PowerPoint parser timeout') from exc
    if result.returncode or len(result.stdout) > 256 * 1024:
        raise ValueError('PowerPoint parser rejected document')
    try:
        parsed = json.loads(result.stdout)
        slides, facts, metadata = parsed['slides'], parsed['facts'], parsed['metadata']
        if (not isinstance(slides, list) or not 1 <= len(slides) <= 100 or not isinstance(facts, list)
                or len(facts) > 20 or not isinstance(metadata, dict)
                or metadata['slide_count'] != len(slides)
                or [s['number'] for s in slides] != list(range(1, len(slides) + 1))
                or any(not isinstance(s['text'], str) for s in slides)
                or sum(len(s['text'].encode('utf-8')) for s in slides) > 100_000
                or any(f['approved'] is not False for f in facts)):
            raise ValueError('invalid PowerPoint parser output')
        return parsed
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('invalid PowerPoint parser output') from exc
