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
const runbook = readFileSync(new URL('docs/buyeros/runbooks/conversation-qa.md', root), 'utf8');

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

test('live recall needs a manual dispatch, reviewed SHA checkout and fixed source', () => {
  assert.match(workflow, /live_model_recall:/);
  assert.match(workflow, /type: boolean/);
  assert.match(workflow, /authorized_spend_usd:[\s\S]*?default: '1'/);
  assert.match(workflow, /model_source_label:/);
  // Pull requests can only run the nonbillable journey: the paid opt-in expression
  // requires a workflow_dispatch event and is not wired to a repository variable.
  assert.match(workflow, /github\.event_name == 'workflow_dispatch' && inputs\.live_model_recall == true/);
  assert.doesNotMatch(workflow, /BUYEROS_QA_MODEL_RECALL: \$\{\{ vars\./);
  // The test code is checked out at the exact reviewed source before credentials.
  assert.match(workflow, /ref: \$\{\{ inputs\.expected_source_sha \|\| github\.event\.pull_request\.head\.sha \}\}/);
  assert.match(workflow, /git rev-parse HEAD/);
  assert.match(workflow, /BUYEROS_NEON_REAL_PASSWORD: \$\{\{ secrets\.BUYEROS_NEON_REAL_PASSWORD \}\}/);
  // The manual paid dispatch uses only the isolated model-QA account, with its own
  // Playwright invocation; the nonbillable account is a separate step.
  assert.match(workflow, /BUYEROS_NEON_REAL_PASSWORD: \$\{\{ secrets\.BUYEROS_MODEL_QA_PASSWORD \}\}/);
  assert.match(workflow, /--grep-invert "authorized model recalls"/);
  assert.match(workflow, /--grep "authorized model recalls"/);
  // A nonbillable rehearsal can reuse the isolated credential, but protected
  // environment variables—not UUID shape—authorize both isolated modes.
  assert.match(workflow, /qa_isolated_rehearsal:/);
  assert.match(workflow, /QA_ISOLATED_WORKSPACE_REQUIRED: \$\{\{ vars\.BUYEROS_MODEL_QA_WORKSPACE_ID \}\}/);
  assert.match(workflow, /QA_ISOLATED_PROJECT_REQUIRED: \$\{\{ vars\.BUYEROS_MODEL_QA_PROJECT_ID \}\}/);
  assert.match(workflow, /QA_MODEL_SOURCE_LABEL_REQUIRED: \$\{\{ vars\.BUYEROS_MODEL_QA_SOURCE_LABEL \}\}/);
  assert.match(workflow, /isolatedWorkspace !== requiredWorkspace/);
  assert.match(workflow, /sourceLabelInput !== requiredLabel/);
  assert.match(workflow, /artifacts\/conversation-qa\/results\*\.xml/);
  assert.match(workflow, /artifacts\/conversation-qa\/\*\.png/);
  // Browser test: two independent manual gates, two threads, cross-thread names.
  assert.match(spec, /BUYEROS_QA_LIVE_RECALL_BUDGET_USD/);
  assert.match(spec, /process\.env\.BUYEROS_QA_MODEL_RECALL!=='true'/);
  assert.match(spec, /BUYEROS_QA_MODEL_SOURCE_LABEL/);
  assert.match(spec, /otherThreadNames/);
  assert.match(spec, /two threads x three turns/);
  assert.match(runbook, /live_model_recall=true/);
  assert.match(runbook, /qa_isolated_rehearsal=true/);
  assert.match(runbook, /BUYEROS_MODEL_QA_WORKSPACE_ID/);
  assert.match(runbook, /BUYEROS_MODEL_QA_SOURCE_LABEL/);
  assert.match(runbook, /product/);
  assert.match(runbook, /authorized_spend_usd=1/);
  assert.match(runbook, /never run automatically[\s\S]{0,40}from a label/);
});
