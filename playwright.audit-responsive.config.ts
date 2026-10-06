import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Separate existing demo parity from live-shaped HTTP/DB checks, retaining owned Linux UI setup.
export default defineConfig({...audit,testMatch:'responsive-accessibility.spec.ts',globalSetup:'./scripts/audit-demo-warmup.mjs',
 reporter:[['list'],['junit',{outputFile:'test-results/q09-responsive.xml'}]],
 webServer:[{command:process.platform==='win32'?'node scripts/serve-audit-ui-fixture.mjs':'pnpm dev',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:false,
 env:{BUYEROS_AUDIT_UI_MODE:'demo',BUYEROS_DEPLOY_TARGET:'',BUYEROS_API_BASE_URL:'',BUYEROS_AUTH0_ISSUER:'',BUYEROS_AUTH0_CLIENT_ID:'',BUYEROS_AUTH0_AUDIENCE:''}}],
});
