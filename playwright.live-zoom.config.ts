import { defineConfig } from '@playwright/test';
import workbench from './playwright.workbench.config';

export default defineConfig({
  ...workbench,
  testMatch: 'api-browser-zoom.spec.ts',
});
