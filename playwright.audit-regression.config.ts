import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Exact affected audits plus the existing native Chromium zoom test; owned fixtures only.
export default defineConfig({...audit,testMatch:['audit-*.spec.ts','api-browser-zoom.spec.ts'],reporter:[['list'],['junit',{outputFile:'test-results/q09-regression.xml'}]]});
