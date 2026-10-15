"""Compare one protected API binding read with the independent production target."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/api'))
from buyeros_api.services.release_binding import database_target_sha256
from runtime_bundle import canonical_json


def collector():
    spec=importlib.util.spec_from_file_location('bound_workspace_reads',ROOT/'scripts/collect-workspace-observations.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def collect_binding(manifest,origin,database_url,token,*,get=None):
    parsed=urlsplit(origin)
    if (parsed.scheme!='https' or parsed.path or parsed.query or parsed.fragment or parsed.username
            or parsed.password or not parsed.hostname or not parsed.hostname.endswith('.vercel.app')
            or parsed.port is not None or len(token)<32 or len(token)>512 or not token.isascii()
            or any(c.isspace() for c in token)):
        raise ValueError('bounded staged origin and probe credential required')
    expected=database_target_sha256(database_url)
    if expected!=manifest['db_target_sha256']:
        raise ValueError('independent database target mismatch')
    status,body=(get or collector().get_json)(origin+'/v1/internal/release-binding',token)
    keys={'schema','source_sha','deployment_id','schema_head','db_target_sha256'}
    if (status!=200 or type(body) is not dict or set(body)!=keys or body['schema']!='buyeros.runtime-db-binding.v1'
            or body['source_sha']!=manifest['source_sha'] or body['deployment_id']!=manifest['candidate_deployment_id']
            or body['db_target_sha256']!=expected or [body['schema_head']]!=manifest['required_heads']):
        raise ValueError('candidate runtime database binding mismatch')
    common={key:manifest[key] for key in ('source_sha','tree_sha','configuration_sha256','db_target_sha256')}
    return {**common,'deployment_id':manifest['candidate_deployment_id'],
            'checked_at':datetime.now(timezone.utc).isoformat(),'evidence_mode':'candidate_runtime',
            'data':{'schema':'buyeros.deployment-db-binding.v1','verified':True,
                    'source_sha':body['source_sha'],'deployment_id':body['deployment_id'],
                    'db_target_sha256':expected,'schema_head':body['schema_head'],
                    'api_origin_sha256':hashlib.sha256(origin.encode()).hexdigest()}}
