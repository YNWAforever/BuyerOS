"""Compose only fresh workspace evidence and write a ciphertext-only immutable artifact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from runtime_bundle import (_release_gate, compose_workspace_receipts, build_workspace_bundle,
                            encrypt_workspace_bundle, canonical_json)


def build_from_directory(directory: Path, source_sha: str) -> dict:
    read = lambda name: _release_gate().read_json(directory/name)
    evidence = read('build-evidence.json')
    if type(evidence) is not dict or set(evidence) != {'ci','artifacts','api_contract_sha256'}:
        raise ValueError('invalid build evidence')
    digest = lambda name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
    manifest = read('manifest.json')
    receipts = compose_workspace_receipts(manifest, read('protected-receipts.json'),
        schema_observation=read('schema-observations.json'),api_observation=read('api-observations.json'),
        binding_observation=read('binding-observations.json'),configuration_observation=read('configuration-observations.json'),
        schema_observation_sha256=digest('schema-observations.json'),api_observation_sha256=digest('api-observations.json'),
        source_sha=source_sha,**evidence)
    return build_workspace_bundle(manifest, receipts, source_sha=source_sha)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output.exists(): raise ValueError('immutable output exists')
        bundle=build_from_directory(args.directory,args.source_sha)
        encrypted=encrypt_workspace_bundle(bundle,os.environ.get('BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY',''))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        descriptor=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as output: output.write(canonical_json(encrypted)+b'\n')
        print(json.dumps({'status':'encrypted_workspace_bundle_created'}))
        return 0
    except Exception:
        print(json.dumps({'error':{'code':'INVALID_OR_UNAVAILABLE_WORKSPACE_BUNDLE'}}))
        return 2


if __name__=='__main__': raise SystemExit(main())
