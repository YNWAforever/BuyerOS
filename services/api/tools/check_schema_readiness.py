"""Read-only schema probe. DSN is accepted only through the secret environment."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.services.schema_readiness import SchemaContract, inspect_schema
from tools.reconcile_staff_membership import unique_keys


def main(argv=None):
    parser=argparse.ArgumentParser(description='Bounded read-only runtime schema readiness')
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.contract.stat().st_size>1024*1024 or args.output.exists():
            raise ValueError('invalid input or existing immutable receipt')
        expected=SchemaContract.model_validate(json.loads(args.contract.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_keys))
        dsn=os.environ.get('BUYEROS_SCHEMA_CHECK_DATABASE_URL','')
        if not dsn.startswith('postgresql://'):
            raise ValueError('schema probe database secret missing')
        async def run():
            engine=create_async_engine(dsn.replace('postgresql://','postgresql+psycopg://',1),connect_args={'connect_timeout':5})
            try:
                async with engine.connect() as connection:
                    return await inspect_schema(connection,expected)
            finally:
                await engine.dispose()
        if sys.platform=='win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        result=asyncio.run(run())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as output:
            output.write(result.model_dump_json(indent=2)+'\n')
        print(json.dumps({'compatible':result.compatible,'blockers':result.blockers}))
        return 0 if result.compatible else 1
    except (ValidationError,ValueError,OSError,UnicodeError):
        print(json.dumps({'error':{'code':'INVALID_SCHEMA_INPUT'}}))
        return 2
    except Exception:
        print(json.dumps({'error':{'code':'SCHEMA_PROBE_UNAVAILABLE'}}))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
