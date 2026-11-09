/** Guards the QA deployment-protection wiring: a protected preview must have a
 * supported bypass path, and the run must fail with an actionable message rather
 * than a locator timeout. Source-level because the journey itself is CI/live-only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const root = new URL('../', import.meta.url);
const config = readFileSync(new URL('playwright.conversation-real.config.ts', root), 'utf8');
const workflow = readFileSync(new URL('.github/workflows/buyeros-conversation-qa.yml', root), 'utf8');
const spec = readFileSync(new URL('tests/e2e/conversation-real-qa.spec.ts', root), 'utf8');

test('the QA browser config forwards an optional deployment-protection bypass', () => {
  assert.match(config, /BUYEROS_QA_PROTECTION_BYPASS/);
  assert.match(config, /'x-vercel-protection-bypass'/);
  assert.match(config, /'x-vercel-set-bypass-cookie'/);
  // The headers must stay conditional: an unprotected candidate sends no token.
  assert.match(config, /protectionBypass\s*\n?\s*\?\s*\{/);
});

test('the QA workflow passes the bypass secret and the journey diagnoses a 401', () => {
  assert.match(workflow, /BUYEROS_QA_PROTECTION_BYPASS: \$\{\{ secrets\.BUYEROS_QA_PROTECTION_BYPASS \}\}/);
  assert.match(workflow, /run: \|[\s\S]*BUYEROS_QA_PROTECTION_BYPASS/);
  // The guard validates the token shape when present.
  assert.match(workflow, /BUYEROS_QA_PROTECTION_BYPASS looks invalid/);
  assert.match(spec, /status\(\)===401/);
  assert.match(spec, /protected by Vercel Authentication/);
});
