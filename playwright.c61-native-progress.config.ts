import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
export default defineConfig({...audit,testMatch:['audit-native-run-progress.spec.ts'],timeout:90_000,
 outputDir:'test-results/c61-native-progress',reporter:[['list'],['junit',{outputFile:'test-results/c61-native-progress.xml'}]]});
