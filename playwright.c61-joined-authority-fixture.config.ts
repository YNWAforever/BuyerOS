import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Local disposable same-data fault regression. Actual preview is a separate gate.
export default defineConfig({...audit,testMatch:['c61-joined-authority-fixture.spec.ts'],outputDir:'test-results/c61-joined-authority-fixture',use:{...audit.use,trace:'on'},reporter:[['list'],['junit',{outputFile:'test-results/c61-joined-authority-fixture.xml'}]]});
