// Execute the retained acceptance scripts with synthetic HTTP responses only.
// Never contact production, authenticate an account, or rewrite historical receipts.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {copyFileSync,existsSync,mkdirSync,mkdtempSync,readFileSync,rmSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import test from 'node:test';

const root=new URL('../',import.meta.url);
const scripts=[
  ['t30-production-acceptance-4181062-20261001.mjs','t30-production-deployment-4181062-20261001.json'],
  ['t30-production-acceptance-12327c7-20261001.mjs','t30-external-merge-production-12327c7-20261001.json'],
];
const neon={provider:'neon',config:{authPath:'/api/auth',socialInitOrigin:'https://ep-offline.neonauth.us-east-2.aws.neon.tech',socialInitPath:'/neondb/auth/sign-in/social/init'}};
const html=publicAuth=>`<html><script type="application/json">${JSON.stringify({publicAuth})}</script></html>`;
const cases=[
  ['public Neon configuration',html(neon),true],
  ['streamed escaped public Neon configuration',`<script>self.rsc.push(${JSON.stringify(`2:${JSON.stringify({publicAuth:neon})}\n`)})</script>`,true],
  ['legacy Auth0 bootstrap only',html({provider:'auth0',issuer:'https://dev-oaug20cdxqqgn1s8.us.auth0.com',clientId:'iVnUZbP4JsjRAJAHob1qmTSlZ0rgZU1R',audience:'https://buyer-os-nu.vercel.app/v1'}),false],
  ['unavailable Neon configuration',html({provider:'unavailable',message:'Ask an administrator to restore sign-in.'}),false],
  ['foreign social sign-in origin',html({...neon,config:{...neon.config,socialInitOrigin:'https://foreign.example.test'}}),false],
  ['private fields in public configuration',html({...neon,config:{...neon.config,cookieSecret:'PRIVATE_COOKIE_CANARY'}}),false],
];

for(const [script,deployment] of scripts)for(const [name,body,accepted] of cases)test(`${script}: ${name}`,()=>{
  mkdirSync(new URL('../work/',import.meta.url),{recursive:true});
  const directory=mkdtempSync(new URL('../work/t30-acceptance-',import.meta.url));
  try{
    for(const file of [script,deployment])copyFileSync(new URL(`artifacts/${file}`,root),join(directory,file));
    const helper=new URL('artifacts/t30-public-neon-bootstrap.mjs',root);
    if(existsSync(helper))copyFileSync(helper,join(directory,'t30-public-neon-bootstrap.mjs'));
    writeFileSync(join(directory,'offline.mjs'),`
      import assert from 'node:assert/strict';
      let calls=0;
      globalThis.fetch=async(url,options)=>{
        assert.equal(options.method,'GET');
        assert.equal(options.redirect,'manual');
        const target=new URL(url);
        assert.equal(target.origin,'https://buyer-os-nu.vercel.app');
        calls++;
        if(target.pathname==='/')return new Response('<title>FIMMICK BuyerOS</title>',{headers:{'content-type':'text/html'}});
        if(target.pathname==='/app')return new Response(${JSON.stringify(body)},{headers:{'content-type':'text/html'}});
        assert.equal(target.pathname,'/v1/workspaces');
        const bearer=options.headers.Authorization;
        assert.ok(bearer===undefined||bearer==='Bearer not-a-jwt');
        return Response.json({code:'UNAUTHENTICATED',message:bearer?'token rejected':'missing bearer token',retryable:false,request_id:'offline-request-'+calls},{status:401});
      };
      process.on('beforeExit',()=>assert.equal(calls,4));
    `);
    const result=spawnSync(process.execPath,['--import',join(directory,'offline.mjs'),join(directory,script)],{encoding:'utf8',timeout:10000});
    assert.equal(result.error,undefined);
    assert.equal(result.status,accepted?0:1,result.stderr||result.stdout);
    const receipt=JSON.parse(readFileSync(join(directory,script.replace(/\.mjs$/,'.json')),'utf8'));
    assert.equal(receipt.passed,accepted?4:3);
    assert.equal(receipt.failed,accepted?0:1);
    assert.equal(receipt.checks[1].public_neon_bootstrap_present,accepted?true:undefined);
    assert.doesNotMatch(result.stdout+result.stderr,/PRIVATE_COOKIE_CANARY/);
  }finally{
    rmSync(directory,{recursive:true,force:true});
  }
});
