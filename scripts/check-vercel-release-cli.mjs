import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const cliRoot = process.argv[2];
assert(cliRoot, 'Pass the installed Vercel package directory');
const root = resolve(cliRoot);
const pkg = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
assert.equal(pkg.version, '54.17.2', 'Review CLI compatibility before changing the release pin');
// This is the same validator and dotenv reader imported by the pinned build command.
const { validateConfig, require_main } = await import(pathToFileURL(join(root, 'dist/chunks/chunk-LUORN5H7.js')).href);
const config = JSON.parse(await readFile(new URL('../vercel.json', import.meta.url), 'utf8'));
const error = validateConfig(config);
assert.equal(error, null, error?.message || 'Release configuration rejected by the pinned CLI');
const cases = {
  CORS: '["https://qa.example.test"]',
  DOLLARS: '$TOKEN ${TOKEN} $(command)',
  BACKSLASH: 'C:\\temp\\file',
  QUOTES: 'say "hello"',
};
const exported = Object.entries(cases).map(([key, value]) => `${key}="${value}"`).join('\n');
assert.deepEqual(require_main().parse(exported), cases, 'Pinned dotenv semantics changed');
for (const [input, expected] of [
  ['a\nb', 'a\nb'], ['a\rb', 'a\\rb'], ['a\\nb', 'a\nb'],
  ['\ufeffpadded\ufeff', 'padded'], ['\u0085keep\u0085', '\u0085keep\u0085'],
  ['\u001ckeep\u001f', '\u001ckeep\u001f'],
]) {
  const value = input.replace(/\n/g, '\\n').replace(/\r/g, '\\r');
  assert.deepEqual(require_main().parse(`VALUE="${value}"`), { VALUE: expected }, 'Pinned normalization semantics changed');
}
console.log('Pinned Vercel CLI accepts BuyerOS Services and expected environment semantics.');
