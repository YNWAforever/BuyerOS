import assert from 'node:assert/strict';
import {test} from 'node:test';
import {marketingHandlers} from './boundary.ts';

const origin = 'http://127.0.0.1:5195';
const env = {MARKETING_ENABLED: '1', MARKETING_SYNTHETIC_MODE: '1', MARKETING_PUBLIC_ORIGIN: origin,
  MARKETING_API_ORIGIN: 'http://127.0.0.1:8013', MARKETING_GATEWAY_KEY: 'synthetic-test-gateway-key-at-least-32-characters'};
const body = {name:'Synthetic Buyer',email:'buyer@example.test',company:'Sample',message:'Synthetic only',locale:'en',website:'',challenge_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'};
const key = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const ack = {receipt_id:'cccccccc-cccc-4ccc-8ccc-cccccccccccc',status:'received',synthetic:true};
function request(options={}) {
  return new Request(origin+'/api/marketing/leads',{method:'POST',body:JSON.stringify(body),headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':key},...options});
}

test('disabled and incomplete configuration never opens transport', async()=>{
  for(const config of [{},{...env,MARKETING_GATEWAY_KEY:''},{...env,MARKETING_SYNTHETIC_MODE:'0'},
    {...env,MARKETING_API_ORIGIN:'http://public.example.com'}, {...env,MARKETING_PUBLIC_ORIGIN:origin+'/'}]) {
    const handlers=marketingHandlers(()=>config,()=>{throw new Error('forbidden transport');});
    const result=await handlers.POST(request());
    assert.equal(result.status,503);
    assert.deepEqual(await result.json(),{code:'intake_unavailable',retryable:true});
  }
});

test('foreign Origin and mismatched request URL fail before transport', async()=>{
  const handlers=marketingHandlers(()=>env,()=>{throw new Error('forbidden transport');});
  for(const supplied of ['https://foreign.test','null',origin+'/',origin+', https://foreign.test','']) {
    const result=await handlers.POST(request({headers:{Origin:supplied,'Content-Type':'application/json','Idempotency-Key':key}}));
    assert.equal(result.status,403);
  }
  assert.equal((await handlers.POST(new Request('http://127.0.0.1:5196/api/marketing/leads',{method:'POST',headers:{Origin:origin}}))).status,403);
});

test('same-origin challenge fetch works without forbidden browser Origin header',async()=>{
  const handlers=marketingHandlers(()=>env,async(url,options)=>{
    assert.equal(url,'http://127.0.0.1:8013/marketing/leads/challenge');
    assert.equal(options.headers.get('Origin'),origin);
    assert.equal(options.headers.get('X-Marketing-Gateway-Key'),env.MARKETING_GATEWAY_KEY);
    assert.equal(options.headers.has('Cookie'),false);
    return Response.json({challenge_id:body.challenge_id});
  });
  const result=await handlers.GET(new Request(origin+'/api/marketing/leads/challenge',{headers:{'Sec-Fetch-Site':'same-origin',Cookie:'private=must-not-forward'}}));
  assert.equal(result.status,200);
  assert.deepEqual(await result.json(),{challenge_id:body.challenge_id});
  for(const metadata of ['cross-site','same-site','none','']) {
    assert.equal((await handlers.GET(new Request(origin+'/api/marketing/leads/challenge',{headers:{'Sec-Fetch-Site':metadata}}))).status,403);
  }
});

test('body cap, content type and malformed payload fail before transport',async()=>{
  const handlers=marketingHandlers(()=>env,()=>{throw new Error('forbidden transport');});
  for(const malformed of [request({body:' '.repeat(8193)}),request({body:'{invalid'}),request({body:'[]'}),
    request({headers:{Origin:origin,'Content-Type':'text/plain','Idempotency-Key':key}}),
    request({headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':'invalid'}})]) {
    assert.equal((await handlers.POST(malformed)).status,422);
  }
  const stream=new ReadableStream({start(controller){controller.enqueue(new Uint8Array(4096));controller.enqueue(new Uint8Array(4097));controller.close();}});
  assert.equal((await handlers.POST(request({body:stream,duplex:'half'}))).status,422);
});

test('ack and retry preserve status and only forward dedicated credentials',async()=>{
  for(const status of [201,200]) {
    const handlers=marketingHandlers(()=>env,async(url,options)=>{
      assert.equal(url,'http://127.0.0.1:8013/marketing/leads');
      assert.equal(options.headers.get('Idempotency-Key'),key);
      assert.equal(options.headers.get('X-Marketing-Gateway-Key'),env.MARKETING_GATEWAY_KEY);
      assert.equal(options.headers.has('Authorization'),false);
      assert.equal(options.headers.has('Cookie'),false);
      assert.equal(options.headers.has('X-Forwarded-For'),false);
      assert.deepEqual(JSON.parse(options.body),body);
      return Response.json(ack,{status});
    });
    const result=await handlers.POST(request({headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':key,Authorization:'Bearer private',Cookie:'private=1','X-Forwarded-For':'192.0.2.1'}}));
    assert.equal(result.status,status);
    assert.equal(result.headers.get('Cache-Control'),'no-store');
    const raw=await result.text();
    assert.deepEqual(JSON.parse(raw),ack);
    assert.equal(raw.includes(env.MARKETING_GATEWAY_KEY),false);
  }
});

test('upstream failure and malformed success cannot invent a receipt',async()=>{
  for(const transport of [async()=>{throw new Error('unavailable');}, async()=>Response.json({status:'received'}),
    async()=>Response.json({...ack,synthetic:false}),async()=>Response.json({detail:'sensitive upstream detail'},{status:500})]) {
    const result=await marketingHandlers(()=>env,transport).POST(request());
    assert.equal(result.status,503);
    assert.deepEqual(await result.json(),{code:'intake_unavailable',retryable:true});
  }
  for(const [status,code,retryable] of [[403,'forbidden',false],[409,'idempotency_conflict',false],[422,'challenge_invalid',false],[429,'rate_limited',true],[503,'intake_unavailable',true]]) {
    const result=await marketingHandlers(()=>env,async()=>Response.json({code,retryable},{status})).POST(request());
    assert.equal(result.status,status);
    assert.deepEqual(await result.json(),{code,retryable});
  }
});
