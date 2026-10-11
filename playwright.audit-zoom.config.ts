import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
export default defineConfig({...audit,testMatch:['api-browser-zoom.spec.ts','audit-daily-ux.spec.ts'],reporter:[['list'],['junit',{outputFile:'test-results/q09-zoom.xml'}]]});
