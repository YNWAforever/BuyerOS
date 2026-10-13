import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loadModule} from './ts-loader.mjs';

const profile=await loadModule('services/live/profile.ts');
const offer={
  company:'Fixture Foods',product:'Thai jasmine rice',value:'Research a potential UK wholesale range.',
  website:'',markets:'GB',language:'en',buyerTypes:['Wholesaler','Importer'],
  must:'Public rice category evidence',nice:'Regional distribution',exclude:'Existing accounts',
  roles:'Rice buyer',confirmed:true,
};

test('UK names and the UK alias resolve to one GB market in both saved payloads',()=>{
  for(const market of ['United Kingdom','UK','Great Britain','Britain','英國','英国','GB']){
    const input={...offer,markets:market};
    assert.deepEqual(profile.toProjectCreate(input).markets,['GB'],market);
    assert.deepEqual(profile.toIcpSaveRequest(input).markets,['GB'],market);
  }
  assert.deepEqual(profile.resolveMarkets('UK, United Kingdom, GB, 英國'),{codes:['GB'],unknown:[]});
});

test('pasted country and language lists accept line breaks and Chinese separators',()=>{
  assert.deepEqual(profile.resolveMarkets('United Kingdom\r\nDE，NL；BE'),{codes:['GB','DE','NL','BE'],unknown:[]});
  assert.deepEqual(profile.resolveLanguages('English\n英文，zh-HK'),{codes:['en','zh-HK'],unknown:[]});
});

test('multi-line buyer criteria preserve commas and slashes within each requirement',()=>{
  const input={...offer,
    must:'Thai / jasmine rice category evidence\r\nWholesaler, importer or distributor',
    nice:'Foodservice / retail reach；Clear, documented procurement remit',
    exclude:'No online-resale / e-commerce partnership pitches\nExisting accounts, subject to reconciliation',
  };
  const saved=profile.toIcpSaveRequest(input);
  assert.deepEqual(saved.requirements.map(({text,category,hard_exclusion})=>({text,category,hard_exclusion})),[
    {text:'Thai / jasmine rice category evidence',category:'must',hard_exclusion:false},
    {text:'Wholesaler, importer or distributor',category:'must',hard_exclusion:false},
    {text:'Foodservice / retail reach',category:'nice',hard_exclusion:false},
    {text:'Clear, documented procurement remit',category:'nice',hard_exclusion:false},
    {text:'No online-resale / e-commerce partnership pitches',category:'exclude',hard_exclusion:true},
    {text:'Existing accounts, subject to reconciliation',category:'exclude',hard_exclusion:true},
  ]);
  assert.deepEqual(saved.requirements,profile.toIcpSaveRequest(input).requirements);
  assert.equal(new Set(saved.requirements.map(row=>row.id)).size,6);
});

test('saved criteria and procurement role titles survive edit and save without fragmenting',()=>{
  const saved={offer_facts:[{field:'product',value:offer.product},{field:'value_proposition',value:offer.value}],
    buyer_types:['wholesaler','importer'],desired_roles:['Rice / ambient procurement','Buying director'],
    requirements:[
      {id:'a',text:'Rice / jasmine portfolio, with public evidence',category:'must',hard_exclusion:false},
      {id:'b',text:'Regional trade reach',category:'must',hard_exclusion:false},
      {id:'c',text:'No online-resale / e-commerce partnership pitches',category:'exclude',hard_exclusion:true},
    ]};
  const edited=profile.offerFromProject(profile.toProjectCreate(offer),saved);
  assert.equal(edited.must,'Rice / jasmine portfolio, with public evidence\nRegional trade reach');
  const resaved=profile.toIcpSaveRequest(edited);
  assert.deepEqual(resaved.requirements.map(({text,category})=>({text,category})),saved.requirements.map(({text,category})=>({text,category})));
  assert.deepEqual(resaved.desired_roles,['Rice / ambient procurement','Buying director']);
  assert.equal(edited.confirmed,false);
  assert.ok(resaved.offer_facts.every(fact=>fact.approved===false));
});

test('role line breaks create separate titles while slash-qualified titles stay intact',()=>{
  const saved=profile.toIcpSaveRequest({...offer,roles:'Rice / ambient category buyer\nPurchasing director; Own-label sourcing'});
  assert.deepEqual(saved.desired_roles,['Rice / ambient category buyer','Purchasing director','Own-label sourcing']);
});

test('country normalization preserves other codes and refuses unknown names',()=>{
  assert.deepEqual(profile.resolveMarkets('Germany, Netherlands/Belgium, US'),{codes:['DE','NL','BE','US'],unknown:[]});
  assert.throws(()=>profile.toProjectCreate({...offer,markets:'United Kingdom, Atlantis'}),/Atlantis/);
  assert.throws(()=>profile.validateLiveOffer({...profile.emptyLiveOffer(),...offer,confirmed:false}),/confirm/i);
});
