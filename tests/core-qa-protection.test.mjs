/** Guards the QA deployment-protection wiring: a protected preview must have a
 * supported bypass path, and the run must fail with an actionable message rather
 * than a locator timeout. Source-level because the journey itself is CI/live-only.
 *
 * The bypass token is intentionally not a context-wide header: it is exchanged
 * once for the bypass cookie inside a Playwright fixture, so browser requests
 * (including cross-origin redirects/assets) only ever carry the cookie. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const root = new URL('../', import.meta.url);
const config = readFileSync(new URL('playwright.conversation-real.config.ts', root), 'utf8');
const fixture = readFileSync(new URL('tests/e2e/qa-protection.fixture.ts', root), 'utf8');
const workflow = readFileSync(new URL('.github/workflows/buyeros-conversation-qa.yml', root), 'utf8');
const spec = readFileSync(new URL('tests/e2e/conversation-real-qa.spec.ts', root), 'utf8');

test('the QA config keeps the bypass token out of context-wide browser headers', () => {
  assert.match(config, /BUYEROS_QA_PROTECTION_BYPASS/);
  assert.doesNotMatch(config, /extraHTTPHeaders/);
  assert.doesNotMatch(config, /x-vercel-protection-bypass/);
  assert.doesNotMatch(config, /x-vercel-set-bypass-cookie/);
  // The one-time exchange lives in the fixture and is optional/conditional.
  assert.match(fixture, /BUYEROS_QA_PROTECTION_BYPASS/);
  assert.match(fixture, /context\.request\.get/);
  assert.match(fixture, /'x-vercel-protection-bypass'/);
  assert.match(fixture, /'x-vercel-set-bypass-cookie'/);
  assert.match(fixture, /if\(protectionBypass&&origin\)/);
  assert.match(spec, /qa-protection\.fixture/);
  assert.doesNotMatch(spec, /extraHTTPHeaders/);
});

test('the QA workflow passes the bypass secret and the journey diagnoses a 401', () => {
  assert.match(workflow, /BUYEROS_QA_PROTECTION_BYPASS: \$\{\{ secrets\.BUYEROS_QA_PROTECTION_BYPASS \}\}/);
  assert.match(workflow, /run: \|[\s\S]*BUYEROS_QA_PROTECTION_BYPASS/);
  // The guard validates the token shape when present.
  assert.match(workflow, /BUYEROS_QA_PROTECTION_BYPASS looks invalid/);
  assert.match(spec, /status\(\)===401/);
  assert.match(spec, /protected by Vercel Authentication/);
});
