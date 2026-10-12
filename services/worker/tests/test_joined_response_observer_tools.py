"""Header receipts must not wait on an aborted/incomplete JSON response body."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('case',['header_with_unfinished_body','body_id_fallback','missing_nonjson_id'])
def test_owned_observer_metadata_receipt_preserves_exact_id_without_waiting_for_unneeded_body(case):
    node=shutil.which('node');assert node,'required Node runtime unavailable; must not skip'
    uri=(ROOT/'tests/e2e/fixtures/c61-response-receipt.mjs').as_uri()
    script='''
import assert from 'node:assert/strict';
const {responseReceipt}=await import(process.argv[2]);
const kind=process.argv[3];let reads=0;
const headers=kind==='missing_nonjson_id'?{'content-type':'text/event-stream'}:{'content-type':'application/json'};
if(kind==='header_with_unfinished_body')headers['x-request-id']='original-owned-header';
const response={url:()=> 'http://127.0.0.1/v1/workspaces/owned/jobs/original',headers:()=>headers,
  request:()=>({method:()=> 'GET'}),status:()=>200,
  json:()=>{reads++;return kind==='header_with_unfinished_body'?new Promise(()=>{}):Promise.resolve({request_id:'original-owned-body'});}};
let timer;
const receipt=await Promise.race([responseReceipt(response),new Promise(resolve=>{timer=setTimeout(()=>resolve('still-waiting'),100);})]);
clearTimeout(timer);assert.notEqual(receipt,'still-waiting','metadata blocked on unfinished body');
assert.equal(receipt.request_id,kind==='header_with_unfinished_body'?'original-owned-header':kind==='body_id_fallback'?'original-owned-body':null);
assert.equal(reads,kind==='body_id_fallback'?1:0);assert.equal(receipt.method,'GET');assert.equal(receipt.status,200);
console.log(JSON.stringify({case:kind,receipt,body_reads:reads}));
'''
    result=subprocess.run([node,'--input-type=module','-',uri,case],input=script,text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['case']==case
