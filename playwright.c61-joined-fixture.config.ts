import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Built UI plus owned legacy Celery/PG fixture only. Real provider/Neon acceptance is separate.
export default defineConfig({...audit,testMatch:['c61-eight-module-fixture.spec.ts'],timeout:600_000,
 outputDir:'test-results/c61-eight-module-fixture',reporter:[['list'],['junit',{outputFile:'test-results/c61-eight-module-fixture.xml'}]]});
