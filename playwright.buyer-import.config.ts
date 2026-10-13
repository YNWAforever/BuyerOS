import {defineConfig} from '@playwright/test';
import management from './playwright.buyer-management.config';
/** Uses the same real API and disposable PostgreSQL fixture as buyer management. */
export default defineConfig({...management,testMatch:'buyer-import.spec.ts',workers:1,
  webServer:(Array.isArray(management.webServer)?management.webServer:[]).map((server,index)=>index===0?{
    ...server,env:{...server.env,BUYEROS_PRIVATE_OBJECT_BACKEND:'postgres',BUYEROS_CLOUDFLARE_EXECUTION_ENABLED:'false'},
  }:server),
});
