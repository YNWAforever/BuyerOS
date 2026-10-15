"""Real encryption and CLI controls; all inputs are owned synthetic evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from test_release_readiness import candidate
from runtime_bundle_fixtures import compose_inputs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_bundle as bundle


def cli():
    path=ROOT/'scripts/build-runtime-bundle.py'
    assert path.is_file(), 'bundle producer CLI is absent'
    spec=importlib.util.spec_from_file_location('bundle_cli',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_complete_composition_requires_live_binding():
    manifest, receipts=candidate()
    inputs=compose_inputs(manifest,receipts)
    result=bundle.compose_workspace_receipts(**inputs)
    assert result['items']['deployment_binding']==receipts['items']['deployment_binding']
    assert bundle.build_workspace_bundle(manifest,result,source_sha=manifest['source_sha'])['receipts']==result


@pytest.mark.parametrize('fault',['binding','api-name','api-duplicate','api-status','api-future','signoff','self-review','reviewer-id'])
def test_incomplete_or_forged_observations_never_compose(fault):
    m,r=candidate();inputs=compose_inputs(m,r)
    if fault=='binding': inputs['binding_observation']['data']['db_target_sha256']='0'*64
    if fault=='api-name': inputs['api_observation']['checks'][0]['code']='invented'
    if fault=='api-duplicate': inputs['api_observation']['checks'][1]=inputs['api_observation']['checks'][0]
    if fault=='api-status': inputs['api_observation']['checks'][0]['observed_status']=401
    if fault=='api-future': inputs['api_observation']['checked_at']='2099-01-01T00:00:00Z'
    canary=inputs['protected_receipts']['items']['workspace_canary']['data']
    if fault=='signoff': canary['human_signoff']=False
    if fault=='self-review': canary['reviewer_id']=canary['initiator_id']
    if fault=='reviewer-id': canary.pop('reviewer_id')
    with pytest.raises(ValueError): bundle.compose_workspace_receipts(**inputs)


def test_intermediate_ciphertext_cannot_become_final_bundle():
    m,r=candidate()
    packet={'schema':'buyeros.private-runtime-observations.v1','source_sha':m['source_sha'],
            'manifest':m,'receipts':r,'private':'PRIVATE_CUSTOMER_OBSERVATION'}
    envelope=bundle.encrypt_observation_packet(packet,'1'*64)
    assert 'PRIVATE_CUSTOMER_OBSERVATION' not in json.dumps(envelope)
    assert bundle.decrypt_observation_packet(envelope,'1'*64)==packet
    with pytest.raises(ValueError): bundle.decrypt_workspace_bundle(envelope,'1'*64)
    with pytest.raises(ValueError): bundle.decrypt_observation_packet(envelope,'2'*64)
    changed=copy.deepcopy(envelope);changed['source_sha']='b'*40
    with pytest.raises(ValueError): bundle.decrypt_observation_packet(changed,'1'*64)


def private_inputs(directory):
    import hashlib
    m,r=candidate();inputs=compose_inputs(m,r)
    files={'manifest.json':m,'protected-receipts.json':inputs['protected_receipts'],
           'schema-observations.json':inputs['schema_observation'],'api-observations.json':inputs['api_observation'],
           'binding-observations.json':inputs['binding_observation'],
           'build-evidence.json':{name:inputs[name] for name in ('ci','artifacts','api_contract_sha256')}}
    for name,value in files.items(): (directory/name).write_text(json.dumps(value),encoding='utf-8')
    canary=files['protected-receipts.json']['items']['workspace_canary']['data']
    for kind in ('api','schema'):
        canary[kind+'_observation_sha256']=hashlib.sha256((directory/(kind+'-observations.json')).read_bytes()).hexdigest()
    (directory/'protected-receipts.json').write_text(json.dumps(files['protected-receipts.json']),encoding='utf-8')
    return m


def test_bundle_cli_publishes_ciphertext_only(tmp_path,monkeypatch,capsys):
    m=private_inputs(tmp_path);out=tmp_path/'published'/'runtime-bundle.json'
    monkeypatch.setenv('BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY','a'*64)
    assert cli().main(['--directory',str(tmp_path),'--source-sha',m['source_sha'],'--output',str(out)])==0
    captured=capsys.readouterr()
    assert 'workspace_canary' not in captured.out+captured.err+out.read_text()
    value=bundle.decrypt_workspace_bundle(json.loads(out.read_text()),'a'*64)
    assert value['manifest']==m
    assert cli().main(['--directory',str(tmp_path),'--source-sha',m['source_sha'],'--output',str(out)])!=0


@pytest.mark.parametrize('fault',['duplicate','stale','future','paid','missing-binding','wrong-source'])
def test_runtime_bundle_rejects_duplicate_and_stale_inputs(tmp_path,monkeypatch,fault,capsys):
    m=private_inputs(tmp_path);out=tmp_path/'public.json'
    path=tmp_path/'manifest.json';manifest=json.loads(path.read_text())
    if fault=='duplicate': path.write_text('{"schema":1,"schema":"PRIVATE_SECRET"}')
    if fault=='paid':
        manifest['activation']['providers']='active';path.write_text(json.dumps(manifest))
    if fault=='wrong-source':
        manifest['source_sha']='0'*40;path.write_text(json.dumps(manifest))
    if fault=='missing-binding': (tmp_path/'binding-observations.json').unlink()
    if fault in ('stale','future'):
        path=tmp_path/'binding-observations.json';value=json.loads(path.read_text())
        value['checked_at']='2020-01-01T00:00:00Z' if fault=='stale' else '2099-01-01T00:00:00Z'
        path.write_text(json.dumps(value))
    monkeypatch.setenv('BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY','a'*64)
    assert cli().main(['--directory',str(tmp_path),'--source-sha',m['source_sha'],'--output',str(out)])!=0
    assert not out.exists()
    assert 'PRIVATE_SECRET' not in capsys.readouterr().out
