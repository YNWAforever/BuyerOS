import {defineConfig} from '@playwright/test';
import supplied from './tests/ui-audit-20261021/playwright.ui-audit.config.mjs';
export default defineConfig({...supplied,
  outputDir:'test-results/t21-public',
  testDir:'./tests/ui-audit-20261021',
  reporter:[['junit',{outputFile:process.env.T21_JUNIT_FILE||'test-results/t21-public.xml'}],['list'],['json',{outputFile:process.env.T21_RESULT_FILE||'.superpowers/t21-20261022/evidence/public-ui.json'}]],
  webServer:{command:'node tests/e2e/fixtures/t21-public-server.mjs',url:'http://127.0.0.1:5197/__owned_health',timeout:30000,reuseExistingServer:false},
});
