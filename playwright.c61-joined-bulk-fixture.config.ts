import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Same owned UI-created data. Process resumption is separate from abrupt crash.
export default defineConfig({...audit,testMatch:['c61-joined-bulk-fixture.spec.ts'],outputDir:'test-results/c61-joined-bulk-fixture',use:{...audit.use,trace:'on'},reporter:[['list'],['junit',{outputFile:'test-results/c61-joined-bulk-fixture.xml'}]]});
