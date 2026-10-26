import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {publishing}=await loadModule('features/marketing/publishing.ts');
const {marketingMetadata,structuredData,jsonLd,sitemapEntries}=await loadModule('features/marketing/seo.ts');
const ready=publishing({siteUrl:'https://marketing.example.test',legalEntity:'Synthetic Example Controller',contactEmail:'contact@example.test',leadRetentionDays:7,privacyApproved:true,termsApproved:true});
test('unapproved publishing remains noindex and has no invented canonical or organization',()=>{
 const draft=publishing({});assert.equal(draft.indexable,false);assert.equal(draft.origin,null);
 assert.deepEqual(marketingMetadata('en','home',draft).robots,{index:false,follow:false});
 assert.equal(marketingMetadata('en','home',draft).alternates,undefined);
 assert.equal(structuredData('en','home',draft).some(v=>v['@type']==='Organization'),false);
 assert.deepEqual(sitemapEntries(draft),[]);
});
test('only approved public origin and legal details produce canonical localized crawl entries',()=>{
 assert.equal(ready.indexable,true);
 const meta=marketingMetadata('en','features',ready);
 assert.equal(meta.alternates.canonical,'https://marketing.example.test/en/features');
 assert.equal(meta.alternates.languages['zh-HK'],'https://marketing.example.test/zh-HK/features');
 assert.equal(meta.openGraph.images[0].url,'https://marketing.example.test/marketing/og-en.png');
 const entries=sitemapEntries(ready);assert.equal(entries.length,16);assert.equal(new Set(entries.map(x=>x.url)).size,16);
 assert.equal(entries.some(x=>/\/(app|auth|api|v1)(\/|$)/.test(new URL(x.url).pathname)),false);
 for(const siteUrl of ['http://example.test','https://user:pass@example.test','https://example.test/path','https://example.test/?x=1','javascript:alert(1)'])assert.equal(publishing({siteUrl}).origin,null);
});
test('homepage FAQ schema describes its four practical questions while the full FAQ keeps ten',()=>{
 const values=structuredData('en','home',ready),faq=values.find(x=>x['@type']==='FAQPage');
 assert.equal(faq.mainEntity.length,4);assert.equal(faq.mainEntity[0].name,'What is BuyerOS?');
 assert.equal(structuredData('en','faq',ready).find(x=>x['@type']==='FAQPage').mainEntity.length,10);
 assert.deepEqual(faq.mainEntity.map(item=>item.name),['What is BuyerOS?','Does it automatically find real buyers?','Will it send messages automatically?','Which languages are supported?']);
 for(const value of values){assert.equal('offers' in value,false);assert.equal('aggregateRating' in value,false);assert.equal('review' in value,false);}
 const script=jsonLd({name:'</script><img src=x>',separator:'\u2028'});assert.equal(script.includes('<'),false);assert.equal(JSON.parse(script).name,'</script><img src=x>');
});
