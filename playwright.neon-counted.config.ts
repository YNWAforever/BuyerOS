// Same actual built SDK cases; separate producer outputs preserve prior evidence.
import {defineConfig} from '@playwright/test';
import base from './playwright.neon-auth.config';
const target=process.env.BUYEROS_N00_TARGET;
export default defineConfig({...base,outputDir:'test-results/neon-counted-transport/'+target+'-ui',
 reporter:[['list'],['junit',{outputFile:'test-results/neon-counted-transport/'+target+'-ui.xml'}]]});
