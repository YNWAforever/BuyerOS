import {defineConfig} from '@playwright/test';
import policy from './playwright.policy.config';
const receipt = process.env.BUYEROS_POLICY_TARGET_RECEIPT;
if (!receipt) throw new Error('Owned policy target receipt required');
const servers = Array.isArray(policy.webServer) ? policy.webServer : policy.webServer ? [policy.webServer] : [];
export default defineConfig({
  ...policy, globalTeardown: undefined, testMatch: 'policy-activation.spec.ts', workers: 1,
  timeout: 90_000, expect: {timeout: 15_000},
  use: {...policy.use, actionTimeout: 15_000, trace: 'retain-on-failure'},
  reporter: [['line'], ['junit', {outputFile: 'test-results/policy-activation.xml'}]],
  webServer: servers.map((server, index) => ({
    ...server, reuseExistingServer: false,
    ...(index === 0 ? {env: {...server.env,
      BUYEROS_E2E_POLICY_ACTIVATION: '1',
      BUYEROS_POLICY_TARGET_RECEIPT: receipt,
      BUYEROS_PAID_ADMISSION_ENABLED: 'false', BUYEROS_DELIVERY_ADMISSION_ENABLED: 'false',
      BUYEROS_CLOUDFLARE_EXECUTION_ENABLED: 'false',
    }} : process.env.BUYEROS_POLICY_BUILT_NEXT === '1'
      ? {command: 'pnpm exec next start --hostname 127.0.0.1 --port 5173'} : {}),
  })),
});
