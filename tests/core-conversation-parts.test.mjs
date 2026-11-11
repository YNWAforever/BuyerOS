import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {readChatThread,readMessagePart,readTurn,internalHref,isUuid}=await import('../features/live/conversation/types.ts');
const {buildTranscript,groupTranscript,collectPanelData,latestToolActivity,panelHasContent,terminalProposals,companyFromEntries}=await import('../features/live/conversation/parts.ts');

const threadId='11111111-1111-4111-8111-111111111111';
const turnId='22222222-2222-4222-8222-222222222222';
const messageId='33333333-3333-4333-8333-333333333333';
function thread(messages){return {id:threadId,version:4,templateId:'custom',title:'Research buyer',createdAt:1000,updatedAt:2000,
  access:'owner',shareCount:0,messages,sources:[{id:'document:doc-1',label:'Offer document'}],runs:[]};}
const userRow={id:messageId,seq:1,role:'user',text:'Research this buyer',created_at:'2026-11-08T01:00:00.000Z',parts:[]};
const assistantRow={id:'44444444-4444-4444-8444-444444444444',seq:2,role:'assistant',text:'Here is the brief.',
  client_message_id:'55555555-5555-4555-8555-555555555555',turn_id:turnId,created_at:'2026-11-08T01:01:00.000Z',
  parts:[{kind:'text',text:'Here is the brief.'},{kind:'citations',items:[{id:'document:doc-1',label:'Offer document',kind:'document',href:'/app/discover/edit?document=doc-1'}]},
    {kind:'tool_activity',call_id:'call-1',capability:'sales-research',title:'Research buyer',state:'completed',started_at:'2026-11-08T01:00:30.000Z',finished_at:'2026-11-08T01:00:59.000Z'},
    {kind:'output_link',output_id:'66666666-6666-4666-8666-666666666666',output_kind:'research_brief',title:'Research brief',revision:1,status:'saved',href:'/app/documents/66666666-6666-4666-8666-666666666666'},
    {kind:'proposal',proposal_id:'77777777-7777-4777-8777-777777777777',capability:'sales-contacts',title:'Enrich buyer',rationale:'Needs verified contact evidence',requires_approval:true,cost:{currency:'USD',amount:0.1}}]};

test('amendment A thread rows normalise role, seq, parts and timestamps; legacy rows read as user notes',()=>{
  const parsed=readChatThread(thread([userRow,assistantRow,{id:'88888888-8888-4888-8888-888888888888',text:'Legacy note'}]));
  assert.ok(parsed);
  assert.equal(parsed.messages[0].role,'user');assert.equal(parsed.messages[0].seq,1);assert.equal(parsed.messages[0].createdAt,Date.parse(userRow.created_at));
  assert.equal(parsed.messages[1].role,'assistant');assert.equal(parsed.messages[1].turnId,turnId);
  assert.equal(parsed.messages[1].clientMessageId,'55555555-5555-4555-8555-555555555555');
  assert.equal(parsed.messages[1].parts.length,5);
  assert.equal(parsed.messages[2].role,'user');assert.deepEqual(parsed.messages[2].parts,[]);assert.equal(parsed.messages[2].seq,null);
  const roundTrip=readChatThread(JSON.parse(JSON.stringify(parsed)));
  assert.ok(roundTrip);
  // Amendment buyer link: the thread envelope carries camelCase buyerId; absent reads null.
  assert.equal(parsed.buyerId,null);
  assert.equal(readChatThread({...thread([userRow]),buyerId:'ae000000-0000-4000-8000-000000000001'}).buyerId,'ae000000-0000-4000-8000-000000000001');
});

test('unknown roles and part kinds degrade safely; malformed parts never throw',()=>{
  const hostile={kind:'future_part',payload:{secret:'x'},__proto__:{polluted:true}};
  assert.deepEqual(readMessagePart(hostile),{kind:'unsupported',source_kind:'future_part'});
  assert.deepEqual(readMessagePart(null),{kind:'unsupported',source_kind:'unknown'});
  assert.deepEqual(readMessagePart({kind:'text',text:'   '}),{kind:'unsupported',source_kind:'text'});
  assert.equal(readMessagePart({kind:'proposal',proposal_id:'p',capability:'c',title:'t'}).requires_approval,true);
  assert.equal(({...readMessagePart({kind:'tool_activity',call_id:'c',capability:'x',title:'t',state:'running'})}).state,'running');
  assert.deepEqual(readMessagePart({kind:'tool_activity',call_id:'c',capability:'x',title:'t',state:'teleported'}),{kind:'unsupported',source_kind:'tool_activity'});
  const hostileThread=readChatThread(thread([{id:messageId,role:'robot',text:'Unknown role row'},{id:'99999999-9999-4999-8999-999999999999',role:'assistant',parts:[hostile]}]));
  assert.ok(hostileThread);
  assert.equal(hostileThread.messages[0].role,'user');
  assert.equal(hostileThread.messages[1].role,'assistant');
  assert.deepEqual(hostileThread.messages[1].parts,[{kind:'unsupported',source_kind:'future_part'}]);
  assert.equal(readTurn({id:turnId,status:'needs_approval',parts:[hostile],notices:[{code:'X',message:'Notice'}]})!==null,true);
  assert.equal(readTurn({id:'not-a-uuid',status:'completed'}),null);
});

test('turn parts render once: persisted rows win, an already represented turn is not duplicated',()=>{
  const parsed=readChatThread(thread([userRow,assistantRow]));
  const turn={id:turnId,status:'completed',parts:[{kind:'text',text:'Here is the brief.'}],notices:[{code:'NOTE',message:'Saved revision 1'}]};
  const entries=buildTranscript(parsed,[turn]);
  assert.equal(entries.length,2);
  assert.equal(entries[1].parts.filter(part=>part.kind==='notice').length,0);
  const unrepresented={id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',status:'needs_approval',
    parts:[{kind:'proposal',proposal_id:'p',capability:'sales-contacts',title:'Enrich buyer',requires_approval:true}],
    notices:[{code:'APPROVAL_REQUIRED',message:'A decision is required'}]};
  const withTurn=buildTranscript(parsed,[turn,unrepresented]);
  assert.equal(withTurn.length,3);
  assert.equal(withTurn[2].parts.at(-1).kind,'notice');
  assert.equal(withTurn[2].turnId,'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
});

test('day grouping groups by local day and keeps undated entries unlabelled',()=>{
  const parsed=readChatThread(thread([userRow,assistantRow,
    {id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',role:'user',text:'Next day',created_at:'2026-11-09T02:00:00.000Z'}]));
  const groups=groupTranscript(buildTranscript(parsed),0);
  assert.equal(groups.length,2);
  assert.equal(groups[0].key,'2026-11-08');assert.equal(groups[0].entries.length,2);
  assert.equal(groups[1].key,'2026-11-09');
  const undated=groupTranscript(buildTranscript(readChatThread(thread([{id:messageId,text:'No timestamp'}]))),0);
  assert.equal(undated.length,1);assert.equal(undated[0].key,'unknown');assert.equal(undated[0].dayStart,null);
});

test('panel data dedupes citations, results and proposals and includes selected sources',()=>{
  const parsed=readChatThread(thread([userRow,assistantRow]));
  const panel=collectPanelData(parsed,buildTranscript(parsed));
  assert.equal(panel.results.length,1);assert.equal(panel.citations.length,1);
  // Buyer identity derives only from a persisted buyer citation, never invented.
  const buyerEntryParts=[{kind:'citations',items:[{id:'buyer:ae000000-0000-4000-8000-000000000001',label:'DeltaGrid',kind:'buyer'}]}];
  const buyerThread=readChatThread({...thread([{id:'be000000-0000-4000-8000-000000000001',seq:1,role:'assistant',text:'DeltaGrid',turn_id:null,parts:buyerEntryParts}]),buyerId:'ae000000-0000-4000-8000-000000000001'});
  assert.deepEqual(companyFromEntries(buildTranscript(buyerThread)),{id:'buyer:ae000000-0000-4000-8000-000000000001',label:'DeltaGrid'});
  assert.equal(companyFromEntries(buildTranscript(parsed)),null);
  // Provider-credit cost with known:false keeps its honest shape (no invented amount).
  const input=readMessagePart({kind:'proposal',proposal_id:'p',capability:'xverum.enrich_company',title:'Enrich',
    rationale:'Needs verified evidence',requires_approval:true,
    cost:{kind:'provider_credits',amount:'0',unit:'credits',may_incur_provider_charges:true,known:false}});
  assert.equal(input.kind,'proposal');assert.equal(input.cost.kind,'provider_credits');
  assert.equal(input.cost.known,false);assert.equal(input.cost.amount,'0');assert.equal(input.cost.unit,'credits');
  // A terminal configuration notice in a later turn makes the earlier proposal inert.
  const terminalThread=readChatThread(thread([userRow,assistantRow,
    {id:'c1000000-0000-4000-8000-000000000001',seq:3,role:'assistant',text:'Cannot run',turn_id:'c2000000-0000-4000-8000-000000000001',
      parts:[{kind:'notice',code:'XVERUM_DISPATCH_NOT_ENABLED',message:'Dispatch is disabled.'},
        {kind:'tool_activity',call_id:'c2000000-0000-4000-8000-000000000001',capability:'sales-research',title:'Research',state:'failed',started_at:'2026-11-08T01:02:00.000Z',error_code:'XVERUM_DISPATCH_NOT_ENABLED'}]}]));
  const terminalEntries=buildTranscript(terminalThread);
  const terminal=terminalProposals(terminalEntries);
  assert.equal(terminal.get('77777777-7777-4777-8777-777777777777').terminal,true);
  assert.equal(terminalProposals(buildTranscript(parsed)).size,0);
  const alt=readMessagePart({part:'output_link',kind:'research_brief',output_id:'66666666-6666-4666-8666-666666666666',title:'Research brief',revision:1,status:'saved',href:'https://evil.invalid/x'});
  assert.equal(alt.kind,'output_link');assert.equal(alt.kind==='output_link'?alt.outputKind:null,'research_brief');assert.equal(alt.href,undefined);
  // The shipped wire nests the output ref under `output` because `kind` is the discriminator.
  const nested=readMessagePart({kind:'output_link',title:'Research brief',href:'/app/documents/66666666-6666-4666-8666-666666666666',
    output:{output_id:'66666666-6666-4666-8666-666666666666',kind:'research_brief',revision:1,status:'saved'}});
  assert.equal(nested.kind,'output_link');assert.equal(nested.href,'/app/documents/66666666-6666-4666-8666-666666666666');
  assert.equal(nested.kind==='output_link'?nested.outputKind:null,'research_brief');
  assert.equal(panel.proposals.length,1);assert.equal(panel.proposals[0].turnId,turnId);
  assert.equal(panel.selectedSources.length,1);
  assert.equal(panelHasContent(panel),true);
  assert.deepEqual(collectPanelData(null,[]),{results:[],citations:[],selectedSources:[],proposals:[]});
  assert.equal(latestToolActivity(buildTranscript(parsed),'sales-research').state,'completed');
  assert.equal(latestToolActivity(buildTranscript(parsed),'sales-contacts'),null);
});

test('only internal /app routes can be navigated from server-provided strings',()=>{
  assert.equal(internalHref('/app/documents/123'),'/app/documents/123');
  assert.equal(internalHref('/app?profile=x'),'/app?profile=x');
  assert.equal(internalHref('https://evil.invalid/app'),undefined);
  assert.equal(internalHref('javascript:alert(1)'),undefined);
  assert.equal(internalHref('//evil.invalid/app'),undefined);
  assert.equal(internalHref('/app\\evil'),undefined);
  assert.equal(internalHref(null),undefined);
  assert.equal(isUuid(threadId),true);assert.equal(isUuid('nope'),false);
});
