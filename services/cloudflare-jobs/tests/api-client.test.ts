import { expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { network } from './network';

const settings = {
  WORKER_API_ORIGIN: 'https://fixture.invalid', WORKER_API_ALLOWED_ORIGINS: '["https://fixture.invalid"]',
  WORKER_CURRENT_KEY_ID: 'fictional-key', WORKER_CURRENT_SECRET: 'fictional-cf05-secret-32-bytes-only',
};

it('signs exact POST path and raw bytes with a fixed protocol vector and no redirect', async () => {
  const { buildSignedRequest } = await import('../src/api-client');
  const request = await buildSignedRequest(settings, 'workerClaim', { runtime_epoch: 1, max_total: 10, time_budget_seconds: 10 },
    { timestamp: 1790812800, nonce: '33333333-3333-4333-8333-333333333333' });
  expect(request.url).toBe('https://fixture.invalid/v1/internal/worker/claim');
  expect(request.method).toBe('POST');
  expect(request.redirect).toBe('manual');
  expect(request.headers.get('authorization')).toBeNull();
  expect(await request.text()).toBe('{"runtime_epoch":1,"max_total":10,"time_budget_seconds":10}');
  expect(request.headers.get('x-buyeros-worker-key-id')).toBe('fictional-key');
  expect(request.headers.get('x-buyeros-worker-nonce')).toBe('33333333-3333-4333-8333-333333333333');
  expect(request.headers.get('x-buyeros-worker-signature')).toBe('95573c79047cbe032259d0613860020ffc6760f141ce1745166ad8519008d469');
});

it('refuses credentials, origin mismatch, URL prefix/query and non-HTTPS outside isolated loopback mode', async () => {
  const { buildSignedRequest } = await import('../src/api-client');
  for (const origin of ['https://evil.invalid', 'https://fixture.invalid/prefix', 'https://fixture.invalid?x=1', 'https://user:pass@fixture.invalid', 'http://fixture.invalid']) {
    await expect(buildSignedRequest({ ...settings, WORKER_API_ORIGIN: origin }, 'workerClaim', { runtime_epoch: 1, max_total: 10, time_budget_seconds: 10 })).rejects.toThrow();
  }
});

it('rejects a redirect response without sending signed headers to its destination', async () => {
  const { callWorkerApi, WorkerApiError } = await import('../src/api-client');
  let leaked = 0;
  network.use(
    http.post('https://fixture.invalid/v1/internal/worker/claim', () => new HttpResponse(null, {
      status: 302, headers: { location: 'https://attacker.invalid/steal' },
    })),
    http.all('https://attacker.invalid/steal', () => { leaked++; return new HttpResponse(null); }),
  );
    await expect(callWorkerApi(settings, 'workerClaim', { runtime_epoch: 1, max_total: 10, time_budget_seconds: 10 }))
      .rejects.toEqual(new WorkerApiError(302));
  expect(leaked).toBe(0);
});

it('bounds API response bytes before parsing or persisting its outcome', async () => {
  const { callWorkerApi } = await import('../src/api-client');
  network.use(http.post('https://fixture.invalid/v1/internal/worker/claim', () => new HttpResponse(' '.repeat(8193))));
    await expect(callWorkerApi(settings, 'workerClaim', { runtime_epoch: 1, max_total: 10, time_budget_seconds: 10 }))
      .rejects.toThrow('response exceeds protocol bound');
});
