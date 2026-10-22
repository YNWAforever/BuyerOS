import {expect, test, type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace = 'e0000000-0000-4000-8000-000000000001';
const project = 'e1000000-0000-4000-8000-000000000001';
const api = 'http://127.0.0.1:8000';
async function signIn(page: Page, subject = 'fixture-admin') {
  const keys = await webcrypto.subtle.generateKey({name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256'}, true, ['sign', 'verify']);
  const publicKey = {...await webcrypto.subtle.exportKey('jwk', keys.publicKey), kid: 'policy-native-fixture', use: 'sig'};
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce = '';
  await page.route('https://oidc.buyeros.test/authorize**', async route => {
    const query = new URL(route.request().url()).searchParams;
    nonce = query.get('nonce') ?? '';
    await route.fulfill({status: 302, headers: {location:
      `http://localhost:5173/auth/callback?code=policy-native-fixture&state=${query.get('state')}`}, body: ''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token', async route => {
    const unsigned = `${encode({alg: 'RS256', kid: 'policy-native-fixture'})}.${encode({
      iss: 'https://oidc.buyeros.test/', aud: 'fixture-public-client', sub: subject, nonce,
      exp: Math.floor(Date.now() / 1000) + 300,
    })}`;
    const signature = await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5', keys.privateKey, new TextEncoder().encode(unsigned));
    await route.fulfill({status: 200, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': '*'},
      body: JSON.stringify({access_token: subject, id_token: `${unsigned}.${Buffer.from(signature).toString('base64url')}`,
        expires_in: 300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json', route => route.fulfill({
    status: 200, contentType: 'application/json', headers: {'Access-Control-Allow-Origin': '*'},
    body: JSON.stringify({keys: [publicKey]}),
  }));
  await page.goto(`/app/settings?workspace=${workspace}&project=${project}`);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('combobox', {name: 'Project', exact: true})).toHaveValue(project);
}
const panel = (page: Page) => page.getByRole('region', {name: 'Controlled purpose activation', exact: true});
async function fillTerms(page: Page) {
  const p = panel(page);
  const now = Date.now();
  await p.getByRole('combobox', {name: 'Purpose', exact: true}).selectOption('contact_research');
  await p.getByLabel('Source domains').fill('rice.example.test');
  const designation = p.getByRole('group', {name: 'Manual actions in this designation', exact: true});
  for (const action of ['observation.append', 'lead.review', 'lead.evidence.read', 'preparation.create',
    'preparation.revise', 'preparation.request_review', 'preparation.review', 'preparation.read'])
    await designation.getByRole('checkbox', {name: action, exact: true}).check();
  await p.getByLabel('Policy version', {exact: true}).fill('synthetic-policy-v1');
  await p.getByLabel('Basis reference', {exact: true}).fill('fixture://basis/not-real-consent');
  await p.getByLabel('Provenance', {exact: true}).fill('Owned synthetic human review');
  await p.getByLabel('Owner evidence reference').fill('fixture://owner/fictional-designation');
  await p.getByLabel('Owner evidence SHA-256').fill('a'.repeat(64));
  await p.getByLabel('Country codes').fill('GB');
  await p.getByLabel('Deletion arrangement reference').fill('fixture://deletion/redaction-and-backup-expiry');
  await p.getByLabel('Valid from (UTC)').fill(new Date(now - 60_000).toISOString().slice(0, 16));
  await p.getByLabel('Expires at (UTC)').fill(new Date(now + 7 * 86_400_000).toISOString().slice(0, 16));
  await p.getByLabel('Application deadline (UTC)').fill(new Date(now + 86_400_000).toISOString().slice(0, 16));
}
async function submit(page: Page) {
  await fillTerms(page);
  const response = page.waitForResponse(r => r.request().method() === 'POST' &&
    new URL(r.url()).pathname.endsWith('/policy-activation-requests'));
  await panel(page).getByRole('button', {name: 'Submit policy application', exact: true}).click();
  const r = await response; expect(r.status()).toBe(201);
  const result = (await r.json()).data;
  const details=panel(page).locator('details');
  await details.getByText('Exact canonical policy terms',{exact:true}).click();
  await expect(panel(page).getByText(result.terms_hash, {exact: true})).toBeVisible();
  await details.getByText('Exact canonical policy terms',{exact:true}).click();
  return result;
}
async function approve(page: Page) {
  const p = panel(page);
  await p.getByLabel('Decision reason').fill('Reviewed every synthetic canonical term; no outreach authority.');
  await p.getByLabel('I reviewed these exact canonical terms and hash').check();
  await p.getByRole('button', {name: 'Approve exact terms', exact: true}).click();
  await expect(p.getByTestId('policy-current-state')).toContainText('approved');
  await expect(p.getByTestId('policy-current-state')).toContainText('permitted');
}

test.beforeEach(async ({request}) => {
  const reset = await request.post(`${api}/fixture/policy-reset`);
  expect(reset.ok()).toBeTruthy();
});
test('admin_submits_and_designated_owner_decides_exact_terms', async ({page, browser, request}) => {
  await signIn(page, 'fixture-requester');
  const original = await submit(page);
  const denied = await request.post(`${api}/v1/workspaces/${workspace}/policy-activation-requests/${original.id}/decisions`, {
    headers: {Authorization: 'Bearer fixture-requester', 'Idempotency-Key': 'fixture-nondesignated-owner'},
    data: {action: 'approve', terms_hash: original.terms_hash, expected_policy_id: null,
      expected_policy_version: null, reason: 'Synthetic requester is not the designated owner'},
  });
  expect(denied.status()).toBe(403);
  const owner = await browser.newContext(), ownerPage = await owner.newPage();
  try {
    await signIn(ownerPage);
    await panel(ownerPage).getByRole('button', {name: `Inspect ${original.id}`, exact: true}).click();
    await approve(ownerPage);
    const counts = await (await request.get(`${api}/fixture/policy-counts`)).json();
    expect(counts).toMatchObject({requests: 1, resolutions: 1, permitted: 1, providers: 0, delivery: 0});
  } finally {await owner.close();}
});
test('same_owner_can_confirm_in_two_audited_actions', async ({page, request}) => {
  await signIn(page); await submit(page); await approve(page);
  expect(await (await request.get(`${api}/fixture/policy-counts`)).json()).toMatchObject({
    submitted_audits: 1, approved_audits: 1, requests: 1, resolutions: 1,
  });
});
test('requester_withdrawal_does_not_revoke_another_active_policy', async ({page, request}) => {
  await signIn(page); await submit(page); await approve(page);
  await panel(page).getByRole('button', {name: 'New policy application', exact: true}).click();
  await submit(page);
  await panel(page).getByLabel('Decision reason').fill('Withdraw this pending synthetic application');
  await panel(page).getByRole('button', {name: 'Withdraw pending application', exact: true}).click();
  await expect(panel(page).getByTestId('policy-current-state')).toContainText('withdrawn');
  await expect(panel(page).getByTestId('policy-current-state')).toContainText('permitted');
  expect(await (await request.get(`${api}/fixture/policy-counts`)).json()).toMatchObject({permitted: 1, requests: 2});
});
test('approved_history_and_expired_policy_are_not_confused', async ({page, request}) => {
  await signIn(page); await submit(page); await approve(page);
  expect((await request.post(`${api}/fixture/policy-expire-authority`)).ok()).toBeTruthy();
  await panel(page).getByRole('button', {name: 'Refresh policy history', exact: true}).click();
  await expect(panel(page).getByTestId('policy-current-state')).toContainText('approved');
  await expect(panel(page).getByTestId('policy-current-state')).toContainText('revoked');
  await page.reload();
  // The existing Auth0 adapter deliberately keeps tokens only in memory.
  // A reload therefore requires an explicit synthetic sign-in before readback.
  await signIn(page);
  await expect(panel(page).getByTestId('policy-history')).toContainText('approved');
  await expect(panel(page).getByTestId('policy-history')).toContainText('revoked');
});
test('duplicate_click_and_unknown_response_recover_one_resource', async ({page, request}) => {
  await signIn(page); await fillTerms(page);
  let lost = false;
  await page.route('**/policy-activation-requests', async route => {
    if (route.request().method() !== 'POST' || lost) return route.continue();
    lost = true;
    await route.fetch(); // Real fixture API committed; only its response is lost.
    await route.abort('failed');
  });
  await panel(page).getByRole('button', {name: 'Submit policy application', exact: true}).dblclick();
  await expect(panel(page).getByText('Policy result is unconfirmed. Check the original request.')).toBeVisible();
  await panel(page).getByRole('button', {name: 'Check original policy result', exact: true}).click();
  await expect(panel(page).getByTestId('policy-current-state')).toContainText('submitted');
  expect(await (await request.get(`${api}/fixture/policy-counts`)).json()).toMatchObject({requests: 1, permitted: 0});
});
test('late_policy_response_cannot_update_another_scope', async ({page, request}) => {
  await signIn(page); await fillTerms(page);
  let release!: () => void;
  const wait = new Promise<void>(done => {release = done;});
  let markCommitted!: () => void, markSettled!: () => void;
  const committed = new Promise<void>(done => {markCommitted = done;});
  const settled = new Promise<void>(done => {markSettled = done;});
  await page.route('**/policy-activation-requests', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    try {
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      markCommitted();
      await wait;
      // Switching workspace aborts the browser's original fetch. Its durable
      // result already exists; fulfilling a canceled request can reject.
      await route.fulfill({response}).catch(() => {});
    } finally {markSettled();}
  });
  const sent = page.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/policy-activation-requests'));
  await panel(page).getByRole('button', {name: 'Submit policy application', exact: true}).click();
  await sent;
  await committed;
  try {
    await page.getByRole('combobox', {name: 'Project', exact: true}).selectOption('e1000000-0000-4000-8000-000000000002');
    await expect(page.getByRole('combobox', {name: 'Project', exact: true}))
      .toHaveValue('e1000000-0000-4000-8000-000000000002');
  } finally {release();}
  await settled;
  await expect(panel(page).getByText('No current controller designation. Ask the data owner.')).toBeVisible();
  await expect(panel(page).getByTestId('policy-history')).not.toContainText('synthetic-policy-v1');
  await expect(panel(page).getByTestId('policy-current-state')).toHaveCount(0);
  expect(await (await request.get(`${api}/fixture/policy-counts`)).json()).toMatchObject({requests: 1, permitted: 0});
});
test('relogin_reads_same_request_and_current_effective_state', async ({page, browser}) => {
  await signIn(page); const original = await submit(page); await approve(page);
  const context = await browser.newContext(), next = await context.newPage();
  try {
    await signIn(next);
    await panel(next).getByRole('button', {name: `Inspect ${original.id}`, exact: true}).click();
    await expect(panel(next).getByTestId('policy-current-state')).toContainText('approved');
    const details=panel(next).locator('details');
    await expect(details).not.toHaveAttribute('open','');
    await details.getByText('Exact canonical policy terms',{exact:true}).click();
    await expect(panel(next).getByText(original.terms_hash, {exact: true})).toBeVisible();
    expect(JSON.parse((await details.locator('pre').textContent())!)).toEqual(original.terms);
  } finally {await context.close();}
});
test('viewer_and_foreign_workspace_cannot_activate', async ({page, request}) => {
  await signIn(page, 'fixture-viewer');
  await expect(panel(page).getByRole('button', {name: 'Submit policy application', exact: true})).toHaveCount(0);
  const foreign = await request.get(`${api}/v1/workspaces/22222222-2222-4222-8222-222222222222/policy-controller-authorities?project_id=${project}`,
    {headers: {Authorization: 'Bearer fixture-admin'}});
  expect(foreign.status()).toBe(404);
});


test('N21-ACCESS-04 summary agrees with exact pending terms and details start collapsed',async({page})=>{
 await signIn(page);const view=await submit(page);
 const p=panel(page),summary=p.getByTestId('policy-business-summary');
 await expect(summary).toContainText('contact_research');
 await expect(summary).toContainText('GB');
 await expect(summary).toContainText('rice.example.test');
 await expect(summary).toContainText('preparation.read');
 await expect(summary).toContainText('7');
 await expect(p.locator('details')).not.toHaveAttribute('open','');
 await p.getByText('Exact canonical policy terms',{exact:true}).click();
 const canonical=await p.locator('details pre').textContent();
 expect(JSON.parse(canonical!)).toEqual(view.terms);
 await expect(p).toContainText('Policy approval does not authorize paid research, enrichment or external sending.');
});
