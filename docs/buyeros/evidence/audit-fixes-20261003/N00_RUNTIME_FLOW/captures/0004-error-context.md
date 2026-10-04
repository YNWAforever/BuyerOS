# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-runtime-flow.spec.ts >> NA01 runtime flow: real-only diagnostic UI has no build-time Auth configuration
- Location: tests\e2e\audit-neon-runtime-flow.spec.ts:3:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'N00 session and token diagnostic' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: 'N00 session and token diagnostic' }) with timeout 5000ms
  - waiting for getByRole('heading', { name: 'N00 session and token diagnostic' })

```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | import {assertProtocolStorage} from '../../scripts/neon-compatibility-harness.mjs';
  3  | test('NA01 runtime flow: real-only diagnostic UI has no build-time Auth configuration',async({page})=>{
  4  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
> 5  |  await page.goto('/compat');await expect(page.getByRole('heading',{name:'N00 session and token diagnostic'})).toBeVisible();
     |                                                                                                               ^ Error: expect(locator).toBeVisible() failed
  6  |  await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  7  |  await expect(page.getByRole('button',{name:'Continue with Google'})).toBeEnabled();
  8  |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));
  9  | });
  10 | 
```