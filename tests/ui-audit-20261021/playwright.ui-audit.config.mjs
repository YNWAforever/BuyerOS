import {defineConfig} from '@playwright/test';

const raw=process.env.BUYEROS_UI_BASE_URL;
const allowed=process.env.BUYEROS_UI_ALLOWED_ORIGIN;
if(!raw||!allowed) throw new Error('Set BUYEROS_UI_BASE_URL and BUYEROS_UI_ALLOWED_ORIGIN to the same reviewed origin.');
const target=new URL(raw);
if(target.origin!==allowed||target.username||target.password||target.search||target.hash||target.pathname!=='/'||
   !(target.protocol==='https:'||(target.protocol==='http:'&&['localhost','127.0.0.1'].includes(target.hostname)))) {
  throw new Error('Exact reviewed origin mismatch.');
}

export default defineConfig({
  testDir:'.',testMatch:'public-ui-audit.spec.mjs',workers:1,retries:0,fullyParallel:false,
  timeout:30000,expect:{timeout:10000},reporter:[['list'],['json',{outputFile:'test-results/ui-audit.json'}]],
  use:{baseURL:target.origin,browserName:'chromium',locale:'en-US',viewport:{width:1440,height:900},
    storageState:{cookies:[],origins:[]},trace:'off',screenshot:'off',video:'off'},
});
