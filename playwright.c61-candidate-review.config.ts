import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Built UI + owned loopback auth fixture, synthetic candidate HTTP responses only.
export default defineConfig({...audit,testMatch:['audit-candidate-review.spec.ts'],timeout:90_000,
 outputDir:'test-results/c61-candidate-review',reporter:[['list'],['junit',{outputFile:'test-results/c61-candidate-review.xml'}]]});
