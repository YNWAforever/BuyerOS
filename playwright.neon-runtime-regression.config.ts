// Reuse the seven strict built fixture cases; preserve every attempt's producer output.
import {defineConfig} from '@playwright/test';
import base from './playwright.neon-auth.config';
const label = String(base.metadata?.n00Target) + '-' + String(base.metadata?.n00RunId);
export default defineConfig({...base, outputDir: 'test-results/neon-real-runtime/' + label + '-ui',
  reporter: [['list'], ['junit', {outputFile: 'test-results/neon-real-runtime/' + label + '-ui.xml'}]]});
