import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

test('checked-in API types match the current OpenAPI contract', () => {
  const result = spawnSync(process.execPath, ['scripts/generate-api-types.mjs', '--check'], {
    cwd: new URL('..', import.meta.url),
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
