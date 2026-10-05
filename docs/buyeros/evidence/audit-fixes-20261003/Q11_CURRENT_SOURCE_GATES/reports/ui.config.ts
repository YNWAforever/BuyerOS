import {defineConfig} from '@playwright/test';
import base from '../../playwright.audit-fixes.config';
import {resolve} from 'node:path';
export default defineConfig({...base,
 testDir:resolve('tests/e2e'),globalTeardown:resolve('test-results/q11-current-source-gates/ui-teardown.ts'),
 outputDir:resolve('test-results/q11-current-source-gates/ui-artifacts'),
 reporter:[['list'],['junit',{outputFile:resolve('test-results/q11-current-source-gates/ui.xml')}]],
 webServer:(base.webServer as {cwd?:string}[]).map(server=>({...server,cwd:resolve(server.cwd??'.')})),
});

