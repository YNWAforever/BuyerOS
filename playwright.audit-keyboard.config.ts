import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Exact keyboard audit discovery, owned HTTP/Postgres and optional compiled UI.
export default defineConfig({...audit,testMatch:['audit-keyboard*.spec.ts','audit-daily-journey.spec.ts'],outputDir:'test-results/q09-keyboard',
  reporter:[['list'],['junit',{outputFile:process.env.BUYEROS_KEYBOARD_REPORT??'test-results/q09-keyboard.xml'}],
    ['json',{outputFile:process.env.BUYEROS_KEYBOARD_JSON_REPORT??'test-results/q09-keyboard.json'}]]});
