import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loadModule} from './ts-loader.mjs';

const {createLiveClient,LiveError}=await loadModule('services/live/client.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
const {saveProfile}=await loadModule('services/live/writes.ts');
const proxy=await import('../app/v1/[...path]/route.ts');
const offer={company:'Fixture Foods',product:'Rice',value:'Wholesale rice supply',website:'',
  markets:'GB',language:'en',buyerTypes:['Wholesaler'],must:'Public rice portfolio',
  nice:'',exclude:'',roles:''};

// Characterization of the hosted failure: a successful response is replaced after
// the write if an HTTP precondition does not match the returned representation.
async function hostedResponse(request,downstream){
  const response=await downstream(request);
  const condition=request.headers.get('If-Match');
  if(response.ok&&condition&&condition!==response.headers.get('ETag')){
    return new Response('Precondition Failed',{status:412});
  }
  return response;
}

async function fixture(run){
  const originalFetch=globalThis.fetch,originalBinding=process.env.BUYEROS_INTERNAL_API_URL;
  process.env.BUYEROS_INTERNAL_API_URL='https://internal.test/';
  const project={id:'p1',version:1,offer_revision:1};
  const profiles=[];
  const receipts=new Map();
  let writes=0;
  globalThis.fetch=async(input,init)=>hostedResponse(new Request(input,init),async request=>{
    const body=await request.json(),path=new URL(request.url).pathname;
    const key=request.headers.get('Idempotency-Key');
    const precondition=request.headers.get('X-BuyerOS-If-Match')??request.headers.get('If-Match');
    const fingerprint=JSON.stringify({path,precondition,body});
    const previous=receipts.get(`${request.method}:${key}`);
    if(previous){
      if(previous.fingerprint!==fingerprint)return Response.json({code:'IDEMPOTENCY_CONFLICT',request_id:'fixture-conflict'},{status:409});
      return Response.json(previous.envelope,{headers:previous.headers});
    }
    let data,headers={};
    if(request.method==='PATCH'){
      if(precondition!==`"${project.version}"`)return Response.json({code:'STALE_REVISION',request_id:'fixture-stale'},{status:412});
      Object.assign(project,body,{version:2,offer_revision:2});writes++;
      data={...project};headers={ETag:'"2"'};
    }else{
      assert.equal(body.basis_offer_revision,project.offer_revision);
      data={id:'i2',number:2,content_hash:'sha256:fixture'};
      profiles.push({...data,...body});
    }
    const envelope={data,request_id:'fixture-save',data_mode:'live'};
    receipts.set(`${request.method}:${key}`,{fingerprint,envelope,headers});
    return Response.json(envelope,{headers});
  });
  const session=new SessionScope({mode:'live',actor:'a1',workspace:'w1',project:'p1'});
  session.setToken('fixture-token');
  const client=createLiveClient(async(path,init)=>hostedResponse(new Request(`https://app.test${path}`,init),
    request=>proxy[request.method](request)));
  const input={mode:'edit',projectId:'p1',expectedProjectVersion:1,basisOfferRevision:1,
    parentIcpVersionId:'i1',offer,session,client,idempotencyKey:'fixture-save-action'};
  try{await run({project,profiles,receipts,input,get writes(){return writes;}});}
  finally{globalThis.fetch=originalFetch;if(originalBinding===undefined)delete process.env.BUYEROS_INTERNAL_API_URL;else process.env.BUYEROS_INTERNAL_API_URL=originalBinding;}
}

test('profile edit reaches the ICP step through both hosted conditional response boundaries',async()=>{
  await fixture(async state=>{
    const result=await saveProfile(state.input);
    assert.equal(result.project.version,2);
    assert.equal(result.icpVersion.id,'i2');
    assert.equal(state.writes,1);
    assert.equal(state.profiles.length,1);
    assert.equal(state.profiles[0].parent_icp_version_id,'i1');
    assert.deepEqual(state.profiles[0].requirements.map(row=>row.text),['Public rice portfolio']);
    const replay=await saveProfile(state.input);
    assert.deepEqual(replay,result);
    assert.equal(state.writes,1);
    assert.equal(state.profiles.length,1);
  });
});

test('a stale project version still rejects the complete profile edit before any saved change',async()=>{
  await fixture(async state=>{
    state.project.version=3;
    await assert.rejects(()=>saveProfile(state.input),error=>error instanceof LiveError&&error.status===412&&error.code==='STALE_REVISION');
    assert.equal(state.project.version,3);
    assert.equal(state.writes,0);
    assert.equal(state.profiles.length,0);
  });
});
