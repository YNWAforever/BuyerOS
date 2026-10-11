"""Explicit privileged writer + verified current admin; default dry-run."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import dispose_engines
from buyeros_api.api.errors import ApiError
from buyeros_api.services.identity_linking import reconcile_identity_manifest

def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate manifest key')
        result[key] = value
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description='Review exact verified identity links; default dry-run')
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.manifest.stat().st_size > 1024 * 1024: raise ValueError('manifest too large')
        manifest=json.loads(args.manifest.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_keys)
        token=os.environ.get('BUYEROS_IDENTITY_ADMIN_TOKEN','')
        writer_dsn=os.environ.get('BUYEROS_IDENTITY_WRITER_DATABASE_URL','')
        if not token: raise ApiError(401,'UNAUTHENTICATED','verified admin token required')
        if not writer_dsn: raise ApiError(503,'IDENTITY_WRITER_UNAVAILABLE','explicit identity writer required')
        if writer_dsn.startswith('postgresql://'):
            writer_dsn=writer_dsn.replace('postgresql://','postgresql+psycopg://',1)
        if not writer_dsn.startswith('postgresql+psycopg://'): raise ValueError('unsupported database driver')
        async def execute():
            engine=create_async_engine(writer_dsn, hide_parameters=True)
            try:return await reconcile_identity_manifest(manifest, token=token, writer_engine=engine, apply=args.apply)
            finally:await engine.dispose();await dispose_engines()
        if sys.platform=='win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        results=asyncio.run(execute())
        print(json.dumps({'apply':args.apply,'results':results}))
        return 0 if all(r['status'] in ('would-link','linked','replayed') for r in results) else 1
    except ApiError as error:
        print(json.dumps({'error':{'code':error.code}}));return 2
    except (ValidationError, ValueError, OSError, UnicodeError):
        print(json.dumps({'error':{'code':'INVALID_MANIFEST'}}));return 2
    except SQLAlchemyError:
        print(json.dumps({'error':{'code':'DATABASE_UNAVAILABLE'}}));return 2

if __name__=='__main__':raise SystemExit(main())
