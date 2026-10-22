import {defineConfig} from '@playwright/test';
import native from './playwright.lead-workflow.config';
const servers=Array.isArray(native.webServer)?native.webServer:[];
export default defineConfig({...native,
 use:{...native.use,ignoreHTTPSErrors:process.env.T21_SYNTHETIC_TLS==='1'},
 testMatch:process.env.T21_POLICY_MODE==='1'?['policy-activation.spec.ts']:['lead-preparations.spec.ts','lead-workflow.spec.ts','lead-evidence.spec.ts','pilot-budget.spec.ts','t21-*.spec.ts'],
 outputDir:'test-results/t21-native',
 reporter:[['list'],['junit',{outputFile:process.env.T21_JUNIT_FILE||'test-results/t21-native.xml'}],['json',{outputFile:process.env.T21_RESULT_FILE||'.superpowers/t21-20261022/evidence/native.json'}]],
 webServer:servers.map((server,index)=>index===1?{...server,command:'node scripts/serve-built-ui-fixture.mjs',
   env:{...server.env,BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_TEST_DATABASE_URL:'',BUYEROS_DATABASE_URL:'',
     BUYEROS_EXECUTION_DATABASE_URL:'',BUYEROS_RUNTIME_ADMIN_DATABASE_URL:'',DATABASE_URL:'',CLOUDFLARE_API_TOKEN:'',
     BUYEROS_DATABASE_MIGRATION_URL:''}}:{...server,env:{...server.env,BUYEROS_E2E_POLICY_ACTIVATION:process.env.T21_POLICY_MODE==='1'?'1':'0',
     // Policy requester has its own designated admin fixture. The lead
     // fixture's role reset is a different scenario and must not run here.
     BUYEROS_E2E_SEED_LEAD_WORKFLOW:process.env.T21_POLICY_MODE==='1'?'0':'1'}}),
});
