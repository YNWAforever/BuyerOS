import {defineConfig} from '@playwright/test';
import audit from './playwright.audit-fixes.config';
// Local built/owned regression for candidate buffers and manifest TTL; real release gates separate.
export default defineConfig({...audit,testMatch:['c61-eight-module-fixture.spec.ts','audit-candidate-review.spec.ts','audit-bulk-manifest.spec.ts','c61-joined-authority-fixture.spec.ts','c61-joined-bulk-fixture.spec.ts'],
 grep:/C61 candidate review|C61 lost entity review|C61 viewer can browse|C61T-11 expired manifest|T30 .*UI-created offer/,
 outputDir:'test-results/c61-react-regression',use:{...audit.use,trace:'on'},reporter:[['list'],['junit',{outputFile:'test-results/c61-react-regression.xml'}]]});
