"""Controlled staff tool: default readonly; credentials never accepted in argv."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from buyeros_api.api.deps import dispose_engines
from buyeros_api.api.errors import ApiError
from buyeros_api.services.staff_onboarding import reconcile_staff_manifest


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate manifest key')
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Review canonical staff memberships; default dry-run')
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.manifest.stat().st_size > 1024 * 1024:
            raise ValueError('manifest too large')
        manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_keys)
        token = os.environ.get('BUYEROS_STAFF_ADMIN_TOKEN', '')
        if not token:
            raise ApiError(401, 'UNAUTHENTICATED', 'admin token required')
        async def execute():
            try:
                return await reconcile_staff_manifest(manifest, token=token, apply=args.apply)
            finally:
                await dispose_engines()
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        results = asyncio.run(execute())
        print(json.dumps({'apply': args.apply, 'results': results}))
        return 0 if all(r['status'] in ('would-create','would-restore','created','restored','replayed','unchanged') for r in results) else 1
    except ApiError as exc:
        print(json.dumps({'error': {'code': exc.code}}));return 2
    except (ValidationError, ValueError, OSError, UnicodeError):
        print(json.dumps({'error': {'code': 'INVALID_MANIFEST'}}));return 2


if __name__ == '__main__':
    raise SystemExit(main())
