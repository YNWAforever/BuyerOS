import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Separate local Unicode/keyboard chain; no real provider, Neon or human acceptance.
export default defineConfig({...audit,testMatch:['c61-unicode-joined-fixture.spec.ts'],outputDir:'test-results/c61-unicode-joined',use:{...audit.use,trace:'on'},reporter:[['list'],['junit',{outputFile:'test-results/c61-unicode-joined.xml'}]]});
