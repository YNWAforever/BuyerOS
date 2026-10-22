import {defineConfig} from '@playwright/test';
import journey from './playwright.t21-journey.config';
const servers=Array.isArray(journey.webServer)?journey.webServer:[];
// These full families prepare their own retained recipient. Do not preload a
// different approval fixture with the same natural key into their owned DB.
const ownTemplate=['reground','template'].includes(process.env.T21_RISK_FAMILY??'');
/** Existing bounded risk regressions; fictional identity/providers and owned DB. */
export default defineConfig({...journey,
 testMatch:['audit-workspace-recovery.spec.ts', 'audit-draft-dirty.spec.ts', 'audit-research-intent.spec.ts', 'audit-native-run-progress.spec.ts', 'audit-research-admission.spec.ts', 'audit-reviewed-list-order.spec.ts', 'audit-candidate-review.spec.ts', 'audit-draft-reground.spec.ts', 'audit-bulk-confirmation.spec.ts', 'audit-auth-entry.spec.ts', 'work-queue-counts.spec.ts', 'audit-access-revocation.spec.ts', 'audit-daily-ux.spec.ts','audit-operations.spec.ts','audit-template-copy.spec.ts'],
 webServer:servers.map((server,index)=>index===0&&ownTemplate?{...server,env:{...server.env,
    BUYEROS_E2E_SEED_DRAFT_APPROVAL:'0',BUYEROS_E2E_SEED_EXPORTS:'0'}}:server),
 outputDir:'test-results/t21-risk',
 reporter:[['list'],['junit',{outputFile:process.env.T21_JUNIT_FILE||'test-results/t21-risk.xml'}],
 ['json',{outputFile:process.env.T21_RESULT_FILE||'test-results/t21-risk.json'}]],
});
