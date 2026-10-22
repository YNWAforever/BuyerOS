import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
const servers=Array.isArray(audit.webServer)?audit.webServer:[];
export default defineConfig({...audit,
 use:{...audit.use,ignoreHTTPSErrors:process.env.T21_SYNTHETIC_TLS==='1'},testMatch:'audit-daily-journey.spec.ts',
 outputDir:'test-results/t21-journey',reporter:[['list'],['json',{outputFile:process.env.T21_RESULT_FILE||'.superpowers/t21-20261022/evidence/thin-journey.json'}]],
 webServer:servers.map((server,index)=>index===0?{...server,env:{...server.env,
   BUYEROS_E2E_STAFF_ISOLATION:'1',BUYEROS_E2E_SEED_DRAFT_APPROVAL:'1',BUYEROS_E2E_SEED_EXPORTS:'1',
   BUYEROS_PAID_ADMISSION_ENABLED:'false',BUYEROS_DELIVERY_ADMISSION_ENABLED:'false',BUYEROS_CLOUDFLARE_EXECUTION_ENABLED:'false',
   BUYEROS_TEST_DATABASE_URL:'',BUYEROS_DATABASE_URL:'postgresql://fixture_unused@127.0.0.1:1/buyeros_test_unopened',BUYEROS_DATABASE_MIGRATION_URL:'',BUYEROS_POLICY_TARGET_RECEIPT:'',
 }}:{...server,command:'node scripts/serve-built-ui-fixture.mjs',env:{...server.env,BUYEROS_STRICT_INTEGRATION:'1',
   BUYEROS_TEST_DATABASE_URL:'',BUYEROS_DATABASE_URL:'',BUYEROS_EXECUTION_DATABASE_URL:'',BUYEROS_RUNTIME_ADMIN_DATABASE_URL:'',DATABASE_URL:'',CLOUDFLARE_API_TOKEN:''}}),
});
