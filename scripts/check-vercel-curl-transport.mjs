// Execute installed command-specific parsers and the 50.28 curl wrapper in a VM.
// No CLI startup, credentials, requests, or native curl execution are permitted.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

function installed(path, version) {
  const root = resolve(path);
  const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'));
  assert.equal(pkg.name, 'vercel');
  assert.equal(pkg.version, version);
  return root;
}
function between(source, start, end) {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, 'pinned source structure changed');
  return source.slice(a, b);
}
const oldRoot = installed(process.argv[2], '50.28.0');
const newRoot = installed(process.argv[3], '54.17.2');
const old = readFileSync(resolve(oldRoot, 'dist/commands-bulk.js'), 'utf8');
const modern = readFileSync(resolve(newRoot, 'dist/commands-bulk.js'), 'utf8');
const argsSource = readFileSync(resolve(oldRoot, 'dist/chunks/chunk-BPNHA3JM.js'), 'utf8');
const tail = ['--disable', '--config', '-', '--silent', '--max-time', '15',
  '--no-location', '--write-out', '\n%{http_code}\n%{content_type}\n%{url_effective}'];
const globals = ['--scope', 'team_fixture', '--global-config', 'PRIVATE_SYNTHETIC_DIR'];
const target = '/v1/workspaces?offset=0&limit=100';
const origin = 'https://fixture.vercel.app';
const argv = ['node', 'vc.js', 'curl', target, '--deployment', origin, ...globals, '--', ...tail];
const telemetry = new Proxy({}, { get: () => () => {} });
const calls = [];
const context = vm.createContext({
  process: { argv },
  // esbuild's module adapters, with only the installed arg module loaded below.
  __commonJS: (map) => { let loadedModule; return () => {
    if (!loadedModule) { loadedModule = { exports: {} }; Object.values(map)[0](loadedModule.exports, loadedModule); }
    return loadedModule.exports;
  }; },
  __toESM: (value) => ({ default: value }),
  output_manager_default: { print() {}, debug() {}, error() { throw Error('unexpected CLI error'); } },
  printError() { throw Error('unexpected parser error'); },
  CurlTelemetryClient: function () { return telemetry; },
  requoteArgs: (s) => s,
  getDeploymentUrlAndToken: async (_client, command, path, opts) => {
    assert.equal(command, 'curl'); assert.equal(path, target);
    assert.equal(opts.deploymentFlag, origin);
    return { fullUrl: origin + target, deploymentProtectionToken: 'fixture-bypass' };
  },
  spawn: (name, flags, options) => {
    calls.push({ name, flags: Array.from(flags), options: { ...options } });
    return { on(event, callback) { if (event === 'close') callback(7); return this; } };
  },
});
vm.runInContext(between(argsSource, 'var require_arg =', '\n//'), context);
vm.runInContext(between(argsSource, 'function getFlagsSpecification(', '\n// src/util/now-error.ts'), context);
vm.runInContext(`var curlCommand = {name:'curl',options:[
  {name:'deployment',type:String},{name:'protection-bypass',type:String},{name:'yes',type:Boolean}]};`, context);
vm.runInContext(between(old, 'function setupCurlLikeCommand(', 'async function getDeploymentUrlAndToken('), context);
vm.runInContext(between(old, 'async function curl(client)', '// src/commands/dns/add.ts'), context);
assert.equal(await context.curl({ argv, telemetryEventStore: {} }), 7);
assert.deepEqual(calls, [{ name: 'curl', flags: [
  '--url', origin + target, '--header', 'x-vercel-protection-bypass: fixture-bypass', ...tail,
], options: { stdio: 'inherit', shell: false } }]);
const modernContext = vm.createContext({});
vm.runInContext(between(modern, 'var VC_STRING_FLAGS', 'function setupCurlLikeCommand('), modernContext);
const regression = modernContext.parseCurlLikeArgs(argv.slice(2), 'curl');
assert.equal(regression.target, target);
assert.deepEqual(Array.from(regression.toolFlags), [...globals, ...tail]);
const moved = modernContext.parseCurlLikeArgs([...globals, ...argv.slice(2, 6), '--', ...tail], 'curl');
assert.equal(moved.target, 'team_fixture');
console.log('PASS: installed 50.28.0 parser isolates global flags and preserves curl stdin/exit transport; 54.17.2 regression reproduced without network');
