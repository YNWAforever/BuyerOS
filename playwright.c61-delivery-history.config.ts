import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Owned built UI journey plus synthetic display-only history, no provider send.
export default defineConfig({...audit,testMatch:['audit-delivery-history.spec.ts'],timeout:600_000,
 outputDir:'test-results/c61-delivery-history',reporter:[['list'],['junit',{outputFile:'test-results/c61-delivery-history.xml'}]]});
