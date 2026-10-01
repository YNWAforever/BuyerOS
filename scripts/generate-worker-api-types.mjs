import {readFile, writeFile, mkdir} from 'node:fs/promises';
import openapiTS, {astToString} from 'openapi-typescript';

const input = new URL('../services/api/contracts/worker.openapi.json', import.meta.url);
const output = new URL('../services/cloudflare-jobs/src/worker-api.generated.ts', import.meta.url);
const value = '// Generated from API-owned internal5 OpenAPI; do not edit.\n' + astToString(await openapiTS(input));
if (process.argv[2] === '--check') {
  if ((await readFile(output, 'utf8')).replaceAll('\r\n', '\n') !== value) throw new Error('Worker API types are stale');
  console.log('Internal worker API types current: 5 operations');
} else if (process.argv[2] === '--write') {
  await mkdir(new URL('.', output), {recursive: true});
  await writeFile(output, value);
  console.log('Generated strict internal worker API types');
} else {
  throw new Error('usage: node scripts/generate-worker-api-types.mjs --check|--write');
}
