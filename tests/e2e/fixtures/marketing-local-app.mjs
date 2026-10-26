import {readFile, lstat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {neonFixtureEnvironmentFor} from './neon-fixture-protocol.mjs';

const path = process.env.MARKETING_FIXTURE_CONFIG;
const runtime = process.env.MARKETING_FIXTURE_RUNTIME ?? 'dev';
if (!path?.startsWith('/tmp/buyeros-marketing-') || !path.endsWith('.json')) throw Error('Explicit owned synthetic fixture handoff required');
const stat = await lstat(path);
if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) !== 0 || stat.uid !== process.getuid()) throw Error('Refusing unowned or public fixture handoff');
const value = JSON.parse(await readFile(path, 'utf8'));
const allowed = new Set(['MARKETING_ENABLED','MARKETING_SYNTHETIC_MODE','MARKETING_REAL_INTAKE_APPROVED','MARKETING_API_ORIGIN','MARKETING_PUBLIC_ORIGIN','MARKETING_GATEWAY_KEY']);
if (!value.node || Object.keys(value.node).some(key => !allowed.has(key)) || value.node.MARKETING_ENABLED !== '1' || value.node.MARKETING_SYNTHETIC_MODE !== '1' || value.node.MARKETING_REAL_INTAKE_APPROVED === '1') throw Error('Only the owned synthetic intake mode is allowed');
if (value.node.MARKETING_PUBLIC_ORIGIN !== 'http://127.0.0.1:5195' || new URL(value.node.MARKETING_API_ORIGIN).hostname !== '127.0.0.1') throw Error('Only loopback fixture origins are allowed');
for (const key of Object.keys(process.env)) if (key.startsWith('BUYEROS_') || key.startsWith('MARKETING_')) delete process.env[key];
Object.assign(process.env, value.node, {
  ...neonFixtureEnvironmentFor('http://127.0.0.1:5195'),BUYEROS_API_BASE_URL: '/', BUYEROS_INTERNAL_API_URL: '',
  MARKETING_SITE_URL: 'http://127.0.0.1:5195',
});
if (runtime === 'built') await import('./marketing-site-built-server.mjs');
else {
  if (runtime !== 'dev') throw Error('Unknown synthetic fixture runtime');
  const entry = new URL('../../../scripts/run-vercel.mjs', import.meta.url);
  process.argv = [process.execPath, fileURLToPath(entry), 'dev', '--host', '127.0.0.1', '--port', '5195'];
  await import(entry.href);
}
