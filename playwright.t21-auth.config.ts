import {defineConfig} from '@playwright/test';
import publicUi from './playwright.t21-public.config';
export default defineConfig({...publicUi,testDir:'./tests/e2e',testMatch:'n21-auth-local.spec.ts',outputDir:'test-results/t21-auth',
 reporter:[['junit',{outputFile:process.env.T21_JUNIT_FILE||'test-results/t21-auth.xml'}],['list'],['json',{outputFile:process.env.T21_RESULT_FILE||'.superpowers/t21-20261022/evidence/auth-browser.json'}]]});
