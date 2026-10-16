import {defineConfig} from '@playwright/test';
import buyer from './playwright.buyer.config';

const servers=Array.isArray(buyer.webServer)?buyer.webServer:buyer.webServer?[buyer.webServer]:[];
export default defineConfig({
  ...buyer,
  testMatch:['lead-evidence.spec.ts','lead-preparations.spec.ts','lead-workflow.spec.ts','pilot-budget.spec.ts'],
  workers:1,
  reporter:[['line'],['junit',{outputFile:'test-results/lead-workflow.xml'}]],
  use:{...buyer.use,timezoneId:'Asia/Hong_Kong'},
  webServer:servers.map((server,index)=>index===0?{...server,env:{...server.env,
    BUYEROS_E2E_SEED_LEAD_WORKFLOW:'1',BUYEROS_DATABASE_MIGRATION_URL:'',
    BUYEROS_PAID_ADMISSION_ENABLED:'false',BUYEROS_DELIVERY_ADMISSION_ENABLED:'false',
    BUYEROS_CLOUDFLARE_EXECUTION_ENABLED:'false',
  }}:{...server,...(process.env.BUYEROS_E2E_FRONTEND==='next'?{
    command:'pnpm exec next dev --webpack --hostname 127.0.0.1 --port 5173',
  }:{})}),
});
