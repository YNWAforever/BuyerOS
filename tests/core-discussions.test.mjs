import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {DiscussionStore}=await loadModule('services/live/discussions.ts');
const scope={actor:'actor',workspace:'workspace',project:'project'};
const id='local-00000000-0000-4000-8000-000000000001';
const messageId='local-00000000-0000-4000-8000-000000000002';
const validThread=()=>({id,templateId:'custom',title:'A question',createdAt:1,updatedAt:1,
  messages:[{id:messageId,text:'A question'}],sources:[]});
const envelope=(threads=[validThread()],changes={})=>({version:1,scope:{...scope},threads,...changes});
const key='buyeros.discussions.v1:actor:workspace:project';

function storage(){
  const entries=new Map(),reads=[],writes=[];
  return {entries,reads,writes,getItem(name){reads.push(name);return entries.get(name)??null;},
    setItem(name,value){writes.push(name);entries.set(name,value);}};
}
function store(enabled=true,context=scope,port=storage()){
  return new DiscussionStore(enabled,context,port);
}

test('local discussions restore only the exact encoded actor, workspace and project namespace',()=>{
  const port=storage(),own=store(true,scope,port),created=own.create('custom','A question');
  assert.match(created.id,/^local-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
  assert.deepEqual(port.writes,[key]);
  assert.deepEqual(store(true,scope,port).getSnapshot().threads,[created]);
  for(const change of [{actor:'other'},{workspace:'other'},{project:'other'}]){
    assert.deepEqual(store(true,{...scope,...change},port).getSnapshot().threads,[]);
  }
  const special=store(true,{actor:'a:b',workspace:'w /',project:'p?'},port);
  special.create('custom','Encoded scope');
  assert.equal(port.writes.at(-1),'buyeros.discussions.v1:a%3Ab:w%20%2F:p%3F');
  assert.deepEqual(JSON.parse(port.entries.get(key)).scope,scope);
});

test('disabled discussions never touch storage and all mutations are no-ops',()=>{
  const port={getItem(){assert.fail('disabled store read storage');},setItem(){assert.fail('disabled store wrote storage');}};
  const own=store(false,scope,port),before=own.getSnapshot();
  let notifications=0;
  own.subscribe(()=>notifications++);
  assert.equal(own.create('custom','A question'),null);
  assert.equal(own.append(id,'Another question'),false);
  assert.equal(own.select(id,{id:'document:one',label:'Offer document'},true),false);
  assert.strictEqual(own.getSnapshot(),before);
  assert.deepEqual(before.threads,[]);
  assert.equal(notifications,0);
});

test('snapshots remain stable until a mutation and subscriptions can be removed',()=>{
  const own=store(),before=own.getSnapshot();
  assert.strictEqual(own.getSnapshot(),before);
  let notifications=0;
  const unsubscribe=own.subscribe(()=>notifications++);
  const thread=own.create('first-project','First question');
  const created=own.getSnapshot();
  assert.notStrictEqual(created,before);
  assert.strictEqual(own.getSnapshot(),created);
  assert.equal(notifications,1);
  assert.equal(own.append('not-a-thread','Question'),false);
  assert.strictEqual(own.getSnapshot(),created);
  unsubscribe();
  assert.equal(own.append(thread.id,'Second question'),true);
  assert.equal(notifications,1);
  assert.deepEqual(before.threads,[]);
  assert.deepEqual(created.threads[0].messages.map(message=>message.text),['First question']);
});

test('creation and append retain only user messages, derive titles and order newest first without networking',(t)=>{
  t.mock.method(globalThis,'fetch',()=>{assert.fail('local discussions must not fetch');});
  const own=store(),prompt='  '+('Question '.repeat(15))+'\n  ';
  const first=own.create('understand-documents',prompt);
  assert.equal(first.title,('Question '.repeat(15)).trim().slice(0,80));
  assert.deepEqual(first.messages.map(message=>message.text),[prompt]);
  const second=own.create('research-market','Second question');
  assert.equal(own.getSnapshot().threads[0].id,second.id);
  assert.equal(own.append(first.id,'Only the user typed this'),true);
  assert.equal(own.getSnapshot().threads[0].id,first.id);
  assert.deepEqual(own.getSnapshot().threads[0].messages.map(message=>message.text),[prompt,'Only the user typed this']);
  assert.ok(own.getSnapshot().threads[0].updatedAt>first.updatedAt);
  assert.match(own.getSnapshot().threads[0].messages[1].id,/^local-[0-9a-f-]{36}$/);
});

test('all approved templates work while unknown templates and invalid messages are refused',()=>{
  const own=store();
  for(const template of ['first-project','understand-documents','research-market','review-buyers','check-company','prepare-follow-up','custom']){
    assert.equal(own.create(template,'User question').templateId,template);
  }
  const count=own.getSnapshot().threads.length,thread=own.getSnapshot().threads[0];
  for(const prompt of ['', '   ', 'x'.repeat(4001),null,{}]){
    assert.equal(own.create('custom',prompt),null);
    assert.equal(own.append(thread.id,prompt),false);
  }
  assert.equal(own.create('send-email','Question'),null);
  assert.equal(own.getSnapshot().threads.length,count);
  assert.ok(own.getSnapshot().notice);
});

test('corrupt, oversized, unsupported and foreign saved data are ignored with a notice',()=>{
  const bad=[
    '{broken json', 'x'.repeat(256*1024+1),
    JSON.stringify(envelope([], {version:0})),
    JSON.stringify(envelope([], {scope:{...scope,actor:'foreign'}})),
    JSON.stringify(envelope([], {scope:{...scope,workspace:'foreign'}})),
    JSON.stringify(envelope([], {scope:{...scope,project:'foreign'}})),
    JSON.stringify(envelope([], {token:'must-not-restore'})),
    JSON.stringify(envelope([], {scope:{...scope,grant:'must-not-restore'}})),
    JSON.stringify(envelope(Array.from({length:31},validThread))),
    JSON.stringify([validThread()]), JSON.stringify(null),
  ];
  for(const raw of bad){
    const port=storage();port.entries.set(key,raw);
    const own=store(true,scope,port);
    assert.deepEqual(own.getSnapshot().threads,[],raw.slice(0,80));
    assert.ok(own.getSnapshot().notice);
    assert.deepEqual(port.writes,[]);
  }
});

test('stored nested fields, identifiers and limits are strictly validated before restoration',()=>{
  const invalidThreads=[
    {...validThread(),hidden:'document contents'},
    {...validThread(),id:'server-thread'},
    {...validThread(),templateId:'send-email'},
    {...validThread(),title:'x'.repeat(81)},
    {...validThread(),createdAt:-1},
    {...validThread(),updatedAt:0},
    {...validThread(),messages:[]},
    {...validThread(),messages:[{id:messageId,text:'question',role:'assistant'}]},
    {...validThread(),messages:[{id:'unsafe/id',text:'question'}]},
    {...validThread(),messages:[{id:messageId,text:'x'.repeat(4001)}]},
    {...validThread(),messages:Array.from({length:101},(_,i)=>({id:`local-00000000-0000-4000-8000-${String(i).padStart(12,'0')}`,text:'question'}))},
    {...validThread(),sources:[{id:'document:one',label:'Offer document',text:'hidden contents'}]},
    {...validThread(),sources:[{id:'fact:one',label:'Private fact value'}]},
    {...validThread(),sources:[{id:'document:one',label:'Research run'}]},
    {...validThread(),sources:[{id:'document:private contents',label:'Offer document'}]},
    {...validThread(),sources:[{id:'document:'+('x'.repeat(200)),label:'Offer document'}]},
    {...validThread(),sources:Array.from({length:101},(_,i)=>({id:`document:${i}`,label:'Offer document'}))},
  ];
  for(const invalid of invalidThreads){
    const port=storage();port.entries.set(key,JSON.stringify(envelope([invalid])));
    const own=store(true,scope,port);
    assert.deepEqual(own.getSnapshot().threads,[]);
    assert.ok(own.getSnapshot().notice);
  }
});

test('saved timestamps must fit a JavaScript Date and timestamp exhaustion refuses mutations',()=>{
  for(const timestamp of [Number.MAX_SAFE_INTEGER,8_640_000_000_000_000,8_640_000_000_000_001]){
    const port=storage();
    port.entries.set(key,JSON.stringify(envelope([{...validThread(),createdAt:timestamp,updatedAt:timestamp}])));
    const own=store(true,scope,port);
    assert.deepEqual(own.getSnapshot().threads,[]);
    assert.ok(own.getSnapshot().notice);
  }
  const port=storage(),timestamp=8_639_999_999_999_999;
  port.entries.set(key,JSON.stringify(envelope([{...validThread(),updatedAt:timestamp}])));
  const own=store(true,scope,port),thread=own.getSnapshot().threads[0];
  assert.doesNotThrow(()=>new Date(thread.updatedAt).toISOString());
  assert.equal(own.create('custom','New question'),null);
  assert.equal(own.append(thread.id,'Follow-up question'),false);
  assert.equal(own.select(thread.id,{id:'fact:profile:fact',label:'Offer fact'},true),false);
  assert.deepEqual(own.getSnapshot().threads,[thread]);
  assert.deepEqual(port.writes,[]);
  assert.match(own.getSnapshot().notice,/timestamp|time/i);
});

test('scope identifiers are bounded before accessing storage or constructing a namespace',()=>{
  for(const field of ['actor','workspace','project']){
    const port=storage(),own=store(true,{...scope,[field]:'a'.repeat(256)},port);
    assert.deepEqual(port.reads,[]);
    assert.equal(own.create('custom','Question'),null);
    assert.ok(own.getSnapshot().notice);
  }
  const port=storage(),own=store(true,{...scope,actor:'a'.repeat(255)},port);
  assert.ok(own.create('custom','Question'));
  assert.equal(port.writes.length,1);
});

test('sources persist generic labels and IDs only and reject hidden content or unsafe labels',()=>{
  const port=storage(),own=store(true,scope,port),thread=own.create('custom','Question');
  const allowed=[{id:'document:one',label:'Offer document'}, {id:'fact:two',label:'Offer fact'},
    {id:'run:three',label:'Research run'},{id:'results:four',label:'Results summary'},
    {id:'fact:five',label:'Approved offer fact'},{id:'fact:six',label:'Candidate offer fact'}];
  for(const source of allowed)assert.equal(own.select(thread.id,source,true),true);
  const written=port.entries.get(key);
  assert.deepEqual(JSON.parse(written).threads[0].sources,allowed);
  const invalid=[{id:'document:seven',label:'Sensitive document title'},
    {id:'document:seven',label:'Offer document',text:'must-never-be-stored'},
    {id:'fact:seven',label:'Offer fact',value:'must-never-be-stored'},
    {id:'run:seven',label:'Results summary'},
    {id:'other:seven',label:'Offer document'},
    {id:'document:'+('a'.repeat(200)),label:'Offer document'},
    {id:'document:has space',label:'Offer document'},
    Object.defineProperty({id:'document:seven',label:'Offer document'},'hidden',{value:'must-never-be-stored'}),
  ];
  for(const source of invalid)assert.equal(own.select(thread.id,source,true),false);
  assert.equal(port.entries.get(key),written);
  const before=own.getSnapshot();
  assert.equal(own.select(thread.id,allowed[0],true),true);
  assert.strictEqual(own.getSnapshot(),before);
  assert.equal(own.select(thread.id,allowed[0],false),true);
  assert.deepEqual(own.getSnapshot().threads[0].sources,allowed.slice(1));
  assert.equal(store(true,scope,port).getSnapshot().threads[0].sources.length,5);
});

test('thread, message and source caps refuse additions without losing existing work',()=>{
  const port=storage(),own=store(true,scope,port);
  for(let i=0;i<30;i++)assert.ok(own.create('custom',`Question ${i}`));
  const before=port.entries.get(key);
  assert.equal(own.create('custom','Over capacity'),null);
  assert.equal(own.getSnapshot().threads.length,30);
  assert.equal(port.entries.get(key),before);
  assert.match(own.getSnapshot().notice,/limit|capacity|full/i);
  const thread=own.getSnapshot().threads[0];
  for(let i=1;i<100;i++)assert.equal(own.append(thread.id,`Question ${i}`),true);
  assert.equal(own.append(thread.id,'Message 101'),false);
  assert.equal(own.getSnapshot().threads[0].messages.length,100);
  for(let i=0;i<100;i++)assert.equal(own.select(thread.id,{id:`fact:${i}`,label:'Offer fact'},true),true);
  assert.equal(own.select(thread.id,{id:'fact:overflow',label:'Offer fact'},true),false);
  assert.equal(own.getSnapshot().threads[0].sources.length,100);
});

test('the byte cap uses UTF-8 size and refuses overflow without evicting existing messages',()=>{
  const port=storage(),own=store(true,scope,port),thread=own.create('custom','Question');
  let accepted=0;
  while(own.append(thread.id,'界'.repeat(4000)))accepted++;
  assert.ok(accepted>10&&accepted<30);
  const saved=port.entries.get(key),before=own.getSnapshot().threads[0].messages;
  assert.ok(Buffer.byteLength(saved,'utf8')<=256*1024);
  assert.equal(own.append(thread.id,'界'.repeat(4000)),false);
  assert.strictEqual(own.getSnapshot().threads[0].messages,before);
  assert.equal(port.entries.get(key),saved);
  assert.match(own.getSnapshot().notice,/limit|capacity|full/i);
  const loaded=store(true,scope,port);
  assert.equal(loaded.getSnapshot().threads[0].messages.length,accepted+1);
  const oversized=envelope([{...validThread(),messages:Array.from({length:25},(_,i)=>({
    id:`local-00000000-0000-4000-8000-${String(i).padStart(12,'0')}`,text:'界'.repeat(4000)}))}]);
  const raw=JSON.stringify(oversized);
  assert.ok(raw.length<256*1024&&Buffer.byteLength(raw,'utf8')>256*1024);
  port.entries.set(key,raw);
  assert.deepEqual(store(true,scope,port).getSnapshot().threads,[]);
});

test('storage errors preserve the in-memory copy and a later successful save persists it',()=>{
  const port=storage();let fail=false;
  const flaky={getItem:name=>port.getItem(name),setItem(name,value){if(fail)throw new Error('quota');port.setItem(name,value);}};
  const own=store(true,scope,flaky),thread=own.create('custom','Saved question');
  fail=true;
  assert.equal(own.append(thread.id,'Unsaved question'),true);
  assert.equal(own.getSnapshot().threads[0].messages.length,2);
  assert.match(own.getSnapshot().notice,/save|storage|tab|memory/i);
  assert.equal(store(true,scope,port).getSnapshot().threads[0].messages.length,1);
  fail=false;
  assert.equal(own.append(thread.id,'Saved again'),true);
  assert.equal(store(true,scope,port).getSnapshot().threads[0].messages.length,3);
});

test('unavailable storage and read errors leave the discussion usable with an honest notice',()=>{
  for(const port of [undefined,{getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}}]){
    const own=new DiscussionStore(true,scope,port);
    assert.match(own.getSnapshot().notice,/storage|tab|memory/i);
    const thread=own.create('custom','Memory question');
    assert.ok(thread);
    assert.equal(own.append(thread.id,'Memory follow-up'),true);
    assert.equal(own.getSnapshot().threads[0].messages.length,2);
    assert.ok(own.getSnapshot().notice);
  }
});

test('a stale tab cannot overwrite threads created by another tab',()=>{
  const port=storage(),first=store(true,scope,port),stale=store(true,scope,port);
  const saved=first.create('custom','Saved in the first tab');
  const before=port.entries.get(key);
  assert.equal(stale.create('custom','Still in the composer'),null);
  assert.equal(port.entries.get(key),before);
  assert.deepEqual(store(true,scope,port).getSnapshot().threads,[saved]);
  assert.match(stale.getSnapshot().notice,/another tab/i);
});

test('stale appends and source changes preserve both persisted and tab-only work',()=>{
  for(const action of ['append','select']){
    const port=storage(),first=store(true,scope,port),thread=first.create('custom','Original');
    const stale=store(true,scope,port);
    first.append(thread.id,'Saved elsewhere');
    const saved=port.entries.get(key),before=stale.getSnapshot().threads;
    const accepted=action==='append'?stale.append(thread.id,'Unsaved message'):
      stale.select(thread.id,{id:'document:one',label:'Offer document'},true);
    assert.equal(accepted,false);
    assert.equal(port.entries.get(key),saved);
    assert.strictEqual(stale.getSnapshot().threads,before);
    assert.match(stale.getSnapshot().notice,/another tab/i);
  }
});

test('Stage 3 requires explicit import confirmation and strips all AI/context bodies',async()=>{
  const {workspaceImport,ConversationThreads}=await loadModule('services/live/conversation-threads.ts');
  const {SessionScope}=await loadModule('services/live/session.ts');
  const thread={...validThread(),sources:[{id:'document:one',label:'Offer document',text:'DOCUMENT_BODY'}],runs:[{id:'00000000-0000-4000-8000-000000000001',label:'Research run',status:'queued',text:'RUN_BODY'}]};
  thread.messages.push({id:'ai',kind:'ai',text:'LIVE_AI_BODY',citations:[{text:'CITATION_BODY'}]});
  assert.throws(()=>workspaceImport(thread,false),/confirmation/);
  const body=workspaceImport(thread,true);
  assert.deepEqual(body.messages,[{text:'A question'}]);assert.deepEqual(body.sources,[{id:'document:one',label:'Offer document'}]);
  assert.doesNotMatch(JSON.stringify(body),/LIVE_AI_BODY|CITATION_BODY|DOCUMENT_BODY|RUN_BODY/);
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'workspace',project:'project'});session.setToken('test');
  let calls=0;const api=new ConversationThreads({request:async()=>{calls++;return {}; }},session,true);
  assert.equal(calls,0,'constructing or listing local threads cannot auto-upload');
  assert.throws(()=>api.import(thread,false),/confirmation/);assert.equal(calls,0);
  await api.import(thread,true);assert.equal(calls,1);
});

test('Stage 3 uncertain writes retain the key and version; scope changes fence late results',async()=>{
  const {ConversationThreads}=await loadModule('services/live/conversation-threads.ts');
  const {SessionScope}=await loadModule('services/live/session.ts');
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'workspace',project:'project'});session.setToken('test');
  const calls=[];let fail=true;
  const api=new ConversationThreads({request:async options=>{calls.push(options);if(fail)throw new Error('offline');return {id:'server'};}},session,true);
  const thread={...validThread(),version:7};
  await assert.rejects(()=>api.append(thread,'Unsaved note'),/offline/);fail=false;
  await api.append(thread,'Unsaved note');
  assert.equal(calls[0].idempotencyKey,calls[1].idempotencyKey);assert.equal(calls[0].ifMatch,'"7"');
  assert.deepEqual(calls[0].body,{text:'Unsaved note'});
  const answer={text:'IN_MEMORY_ACCEPTED_REPLY',status:'needs_review',fixture:false,citations:[]};
  api.retainReply(thread.id,'first-question',answer);api.retainReply(thread.id,'second-question',answer);
  assert.strictEqual(api.acceptedReply(thread.id,'first-question'),answer);
  assert.equal(api.acceptedReply('another-thread','first-question'),undefined);
  api.forgetReply(thread.id,'second-question');assert.strictEqual(api.acceptedReply(thread.id,'first-question'),answer);
  session.next({project:'other'});await assert.rejects(()=>api.get('server'),/scope changed/);assert.equal(calls.length,2);
  assert.equal(api.acceptedReply(thread.id,'first-question'),undefined,'scope changes clear accepted answers');
  api.retainReply(thread.id,'late-result',answer);assert.equal(api.acceptedReply(thread.id,'late-result'),undefined);
  const current=new ConversationThreads({request:()=>assert.fail('cache-only checks cannot fetch')},session,true);
  current.retainReply(thread.id,'question',answer);current.forgetReply();
  assert.equal(current.acceptedReply(thread.id,'question'),undefined,'permission loss clears accepted answers');
  current.retainReply(thread.id,'question',answer);session.setToken(undefined);
  assert.equal(current.acceptedReply(thread.id,'question'),undefined,'sign-out clears accepted answers');
  const disabled=new ConversationThreads({request:()=>assert.fail('OFF networking')},session,false);
  await assert.rejects(()=>disabled.list(),/scope changed/);
});

test('removing a local copy is explicit and still respects the stale-tab fence',()=>{
  const port=storage(),own=store(true,scope,port),thread=own.create('custom','Keep until removed');
  const other=store(true,scope,port);other.append(thread.id,'Another tab');
  assert.equal(own.remove(thread.id),false);assert.equal(own.getSnapshot().threads.length,1);
  const current=store(true,scope,port);assert.equal(current.remove(thread.id),true);
  assert.equal(store(true,scope,port).getSnapshot().threads.length,0);
});
