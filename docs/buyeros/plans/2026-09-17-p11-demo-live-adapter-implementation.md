# P11 Demo/Live Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under a dependency waiver.

**Goal:** Introduce an explicit demo/live data-source boundary in the browser client so the preserved screen shell can serve a live tenant without ever mixing live data with demo fixtures.

**Architecture:** Mode is resolved once on the server and passed down read-only; the client never controls it. Pure logic lives in dependency-free `.ts` modules (mode resolution, mapping, transport, session scope) so it is testable with the repository's node-script convention; React components are thin renderers over them. The live path is gated off, exercised against a stubbed fetch, and never falls back to demo data.

**Tech Stack:** TypeScript, React 19 / Next 16 (vinext on Cloudflare Workers), Node 24 for the checks script, the existing `typescript` dependency for on-the-fly transpilation. **No new dependency is added.**

## Global Constraints

- Spec: `docs/buyeros/specs/2026-09-17-p11-demo-live-adapter-design.md`. Contract: `docs/buyeros/contracts/openapi.proposed.yaml`. Task: `docs/buyeros/tasks/BO-006-separate-demo-state-from-authenticated-live-adapters.md`.
- Branch `p11-demo-live-adapter` from `main` @ `3f10f41`.
- Plan-only artifact: no remote commits/pushes, deploys, cloud resources, real-data migrations, paid calls, mailboxes, or sends.
- **Mode is a server decision.** No UI control and no browser-storage key changes it. `apiBaseUrl` absent or empty means `demo`; present means `live`.
- **A failure never falls back to demo data.** No error path may consult the demo store or fixtures.
- **`empty` and `unavailable` are distinct states** and are rendered differently. A missing list must never read as "we searched and found nothing".
- **Live mode never loads or writes the demo storage keys** (`buyeros-demo-v1`, `buyeros-drafts-v1`, `buyeros-prefs-v1`) and never constructs the demo `Store`.
- **Tokens stay in memory**: never in `localStorage`, never in a URL, never logged.
- **Reads only**: `listWorkspaces`, `listProjects`, `getProject`, `listICPVersions`, `listBuyers`. No live writes this phase.
- **WebMCP stays synthetic**: the `modelContext` tool is registered in demo mode only.
- Mapping is strict: a payload missing a required field raises a typed error and is never coerced to an empty value.
- **No new dependency.** Tests run as `node tests/live-adapter-checks.mjs`; the existing 11 `tests/domain-checks.mjs` checks must stay green.
- **Runtime checks are not a type check.** The check harness transpiles with `tsc`'s emit but does not type-check, so a duplicate identifier, shadowed method or bad signature can stay green until another module calls it. Every task must also run `npx eslint <changed files>` clean, and type-check the modules it changes using the repository's own module/resolution pair (mixing `--moduleResolution nodenext` with `--module ESNext` is an error, TS5110):

  ```
  npx tsc --noEmit --strict --module esnext --moduleResolution bundler --target ES2022 <changed .ts files>
  ```

  **Type-invalid TypeScript is a defect even when the runtime checks pass.**
- Every unexecuted check is **NOT RUN**.

**Existing interfaces this plan consumes (already implemented):**
- `services/contracts.ts`: `Store`, `Company`, `ApiError`, `ApiResponse<T>`, `Page<T>`.
- `data/demo/fixtures.ts`: `seed(): Store`, `base`. `lib/id.ts`: `uid()`.
- `services/generated/buyeros-api.ts`: generated types from the contract (`paths`, `operations`).
- The API's read surface from P9/P10, including its response envelope `{data, request_id, data_mode:"live"}` and error envelope `{code, message, request_id, retryable}`.
- `tests/domain-checks.mjs`: the existing node-script check convention (11 checks).

**Refinement recorded in this plan (not in the spec's wording):** the spec names `features/providers/data-mode.tsx` and `workspace-session.tsx` as the homes of mode and session logic. This plan puts the *logic* in dependency-free `services/live/mode.ts` and `services/live/session.ts`, leaving the two `.tsx` files as thin context providers. The spec's §F anticipates exactly this ("the components are thin renderers over those functions") and §A asks for units that "can be understood and tested independently"; a `.tsx` module cannot be loaded by the node-script checks.

---

### Task 1: Shared TS test loader, mode resolution and availability

**Files:**
- Create: `tests/ts-loader.mjs`
- Modify: `tests/domain-checks.mjs` (use the shared loader; keep 11 checks green)
- Create: `tests/live-adapter-checks.mjs`
- Create: `services/live/mode.ts`

**Interfaces:**
- Produces: `tests/ts-loader.mjs` exporting `loadModule(path) -> Promise<module>`; `services/live/mode.ts` exporting `type DataMode = 'demo'|'live'`, `type Availability = 'available'|'unavailable'|'not_configured'|'denied'`, `type Section`, `resolveMode(apiBaseUrl?: string | null): DataMode`, `availabilityFor(mode: DataMode, section: Section, liveReady?: boolean): Availability`, `LIVE_SECTIONS: Section[]`.
- Consumes: nothing from later tasks.

- [ ] **Step 0: Provide the test toolchain (prerequisite)**

The check scripts import `typescript` from the repository's `node_modules`, which is **not committed and not currently installed** (`scripts/install-pnpm.sh` is Linux-only — it requires `flock` and GNU `timeout` — so `npm run install:ci` cannot run here). Install with plain pnpm at the repository root:

```bash
pnpm install
```

This is gitignored build output: it must not add or change any tracked file, and it must not modify `pnpm-lock.yaml` (if it does, stop and report — the lockfile is not in scope). Verify the toolchain is present before continuing:

```bash
node -e "console.log(require('typescript').version)"
```

Expected: a `5.x` version, no error. If the install cannot complete, stop and report **BLOCKED** with the output — do not vendor `typescript` or hand-roll a transpiler.

- [ ] **Step 1: Write the failing checks**

Create `tests/live-adapter-checks.mjs`:

```js
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

let checks=0;
// Async by necessity: several checks await a deferred response. A sync harness would let those
// assertions run after the summary and turn a failure into an unhandled rejection.
async function test(name,fn){await fn();checks++;console.log('PASS '+name);}
const mode=await loadModule('services/live/mode.ts');

await test('apiBaseUrl absent or blank resolves to demo',()=>{
  assert.equal(mode.resolveMode(undefined),'demo');
  assert.equal(mode.resolveMode(null),'demo');
  assert.equal(mode.resolveMode(''),'demo');
  assert.equal(mode.resolveMode('   '),'demo');
});

await test('a configured apiBaseUrl resolves to live',()=>{
  assert.equal(mode.resolveMode('https://api.example.test'),'live');
});

await test('demo mode makes every section available, live mode does not',()=>{
  const sections=['overview','discovery','lists','outreach','results','settings'];
  for(const s of sections)assert.equal(mode.availabilityFor('demo',s),'available');
  assert.equal(mode.availabilityFor('live','overview'),'available');
  for(const s of ['discovery','lists','outreach','results'])assert.equal(mode.availabilityFor('live',s),'unavailable');
});

await test('live without a ready session reports not_configured, never available',()=>{
  assert.equal(mode.availabilityFor('live','overview',false),'not_configured');
  assert.equal(mode.availabilityFor('live','overview',true),'available');
});

await test('unavailable and not_configured are distinct states',()=>{
  assert.notEqual(mode.availabilityFor('live','outreach'),mode.availabilityFor('live','overview',false));
});

console.log(`${checks} live adapter checks passed`);
```

- [ ] **Step 2: Run to verify it fails**

Run (repo root): `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../tests/ts-loader.mjs`.

- [ ] **Step 3: Create the shared loader and repoint the existing checks**

Create `tests/ts-loader.mjs` by extracting the loader currently inlined in `tests/domain-checks.mjs` (lines 1-6), unchanged in behaviour:

The existing loader is **synchronous** — it builds `data:` URLs recursively and caches strings, which is why nested imports resolve. Extraction must preserve that shape exactly; making it async breaks the recursion.

```js
// tests/ts-loader.mjs
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const cache=new Map();

/** Transpile a .ts file (and its `@/` and relative imports) into a data: URL. Synchronous. */
export function moduleUrl(file){
  const abs=path.resolve(file);
  if(cache.has(abs))return cache.get(abs);
  let js=ts.transpileModule(fs.readFileSync(abs,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
  js=js.replace(/from\s*(['"])([^'"]+)\1/g,(all,q,spec)=>{
    let f=spec.startsWith('@/')?path.resolve(spec.slice(2)):path.resolve(path.dirname(abs),spec);
    if(!path.extname(f))f+='.ts';
    return 'from '+JSON.stringify(moduleUrl(f));
  });
  const u='data:text/javascript;base64,'+Buffer.from(js).toString('base64');
  cache.set(abs,u);
  return u;
}

/** Import a .ts module by path. */
export async function loadModule(file){ return import(moduleUrl(file)); }
```

Then in `tests/domain-checks.mjs`, replace only the loader block — the `fs`/`path`/`ts` imports, the `cache` map and the `url` function — with:

```js
import {moduleUrl} from './ts-loader.mjs';
```

Keep `import assert from 'node:assert/strict';` (it is used by every check), and change each `url('...')` call to `moduleUrl('...')`. The three call sites are `data/demo/fixtures.ts`, `services/mock-client.ts` and `services/run-engine.ts`. The 11 existing checks and their assertions must not change.

- [ ] **Step 4: Implement `services/live/mode.ts`**

```ts
export type DataMode = 'demo' | 'live';
/** Never inferred from empty data.
 *  unavailable = no backing operation; not_configured = live is off and no request was made;
 *  denied = refused (a 401 means sign-in is required; a 403 is a permission refusal);
 *  transient = retryable (429/503/network); not_found = absent from this workspace. */
export type Availability = 'available' | 'unavailable' | 'not_configured' | 'denied' | 'transient' | 'not_found';
export type Section = 'overview' | 'discovery' | 'lists' | 'outreach' | 'results' | 'settings';

/** Sections the live API can back in this phase. Everything else is explicitly unavailable. */
export const LIVE_SECTIONS: Section[] = ['overview', 'settings'];

export function resolveMode(apiBaseUrl?: string | null): DataMode {
  return apiBaseUrl && apiBaseUrl.trim() ? 'live' : 'demo';
}

export function availabilityFor(mode: DataMode, section: Section, liveReady: boolean = true): Availability {
  if (mode === 'demo') return 'available';
  if (!LIVE_SECTIONS.includes(section)) return 'unavailable';
  return liveReady ? 'available' : 'not_configured';
}
```

- [ ] **Step 5: Run both check scripts to verify they pass**

Run: `node tests/live-adapter-checks.mjs` → Expected: `5 live adapter checks passed`.
Run: `node tests/domain-checks.mjs` → Expected: `11 domain checks passed` (unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/ts-loader.mjs tests/domain-checks.mjs tests/live-adapter-checks.mjs services/live/mode.ts
git commit -m "feat(live): mode resolution and availability with shared check loader"
```

---

### Task 2: Strict live read models

**Files:**
- Create: `services/live/mapping.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `LiveWorkspace`, `LiveProject`, `LiveIcpVersion`, `LiveBuyer` interfaces; `MapError` class; `toWorkspaces(data: unknown): LiveWorkspace[]`, `toProjects(data: unknown): LiveProject[]`, `toIcpVersions(data: unknown): LiveIcpVersion[]`, `toBuyers(data: unknown): LiveBuyer[]`.
- Consumes: `services/live/mode.ts` (Task 1) only for the checks file layout.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const map=await loadModule('services/live/mapping.ts');

await test('workspaces map to the narrow model',()=>{
  const payload={items:[{id:'ws-1',name:'Acme',roles:['viewer'],data_mode:'live'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toWorkspaces(payload),[{id:'ws-1',name:'Acme',roles:['viewer']}]);
});

await test('projects map to the narrow model',()=>{
  const payload={items:[{id:'p-1',name:'Sensors',status:'active'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toProjects(payload),[{id:'p-1',name:'Sensors',status:'active'}]);
});

await test('icp versions map approved_at to approvedAt and keep the hash',()=>{
  const payload={items:[{id:'i-1',number:2,content_hash:'sha256:aa',status:'approved',approved_at:'2026-09-01T00:00:00Z'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toIcpVersions(payload),[{id:'i-1',number:2,contentHash:'sha256:aa',status:'approved',approvedAt:'2026-09-01T00:00:00Z'}]);
});

await test('buyers map to the narrow model and keep a null note as null',()=>{
  const payload={items:[{id:'b-1',name:'Example GmbH',note:null}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toBuyers(payload),[{id:'b-1',name:'Example GmbH',note:null}]);
});

await test('a missing required field raises instead of becoming an empty value',()=>{
  assert.throws(()=>map.toBuyers({items:[{id:'b-1',note:null}],offset:0,limit:1,total:1}),map.MapError);
  assert.throws(()=>map.toWorkspaces({items:[{name:'no id'}]}),map.MapError);
  assert.throws(()=>map.toBuyers({items:null}),map.MapError);
  assert.throws(()=>map.toBuyers(undefined),map.MapError);
});

await test('every mapper enforces its required fields',()=>{
  assert.throws(()=>map.toProjects({items:[{id:'p-1',name:'Sensors'}]}),map.MapError);
  assert.throws(()=>map.toIcpVersions({items:[{id:'i-1',content_hash:'h',status:'s'}]}),map.MapError);
  assert.throws(()=>map.toBuyers({items:['not-an-object']}),map.MapError);
});

await test('a workspace missing roles raises rather than defaulting to an empty list',()=>{
  assert.throws(()=>map.toWorkspaces({items:[{id:'w-1',name:'Acme'}]}),map.MapError);
  assert.throws(()=>map.toWorkspaces({items:[{id:'w-1',name:'Acme',roles:['viewer',7]}]}),map.MapError);
});

await test('a version without an approval date maps to null, not an error',()=>{
  assert.deepEqual(
    map.toIcpVersions({items:[{id:'i-1',number:1,content_hash:'h',status:'saved'}]}),
    [{id:'i-1',number:1,contentHash:'h',status:'saved',approvedAt:null}],
  );
});

await test('an empty page is empty, not an error',()=>{
  assert.deepEqual(map.toBuyers({items:[],offset:0,limit:0,total:0}),[]);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/mapping.ts`.

- [ ] **Step 3: Implement `services/live/mapping.ts`**

```ts
export interface LiveWorkspace { id: string; name: string; roles: string[]; }
export interface LiveProject { id: string; name: string; status: string; }
export interface LiveIcpVersion { id: string; number: number; contentHash: string; status: string; approvedAt: string | null; }
export interface LiveBuyer { id: string; name: string; note: string | null; }

/** A payload did not match the contract shape. Never swallowed into an empty value. */
export class MapError extends Error {}

function page(data: unknown): unknown[] {
  if (typeof data !== 'object' || data === null) throw new MapError('expected a page object');
  const items = (data as {items?: unknown}).items;
  if (!Array.isArray(items)) throw new MapError('expected page.items to be an array');
  return items;
}

/** Every field passed here is required: a missing or empty value raises, never becomes ''. */
function str(row: Record<string, unknown>, key: string): string {
  const v = row[key];
  if (typeof v === 'string' && v.length) return v;
  throw new MapError(`missing required field: ${key}`);
}

/** A required list of strings. Absent, non-array or wrong-typed elements all raise. */
function strList(row: Record<string, unknown>, key: string): string[] {
  const v = row[key];
  if (!Array.isArray(v)) throw new MapError(`missing required field: ${key}`);
  for (const item of v) {
    if (typeof item !== 'string') throw new MapError(`expected string elements in: ${key}`);
  }
  return v as string[];
}

function rows(data: unknown): Record<string, unknown>[] {
  return page(data).map((item) => {
    if (typeof item !== 'object' || item === null) throw new MapError('expected an object row');
    return item as Record<string, unknown>;
  });
}

export function toWorkspaces(data: unknown): LiveWorkspace[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    name: str(r, 'name'),
    roles: strList(r, 'roles'),
  }));
}

export function toProjects(data: unknown): LiveProject[] {
  return rows(data).map((r) => ({ id: str(r, 'id'), name: str(r, 'name'), status: str(r, 'status') }));
}

export function toIcpVersions(data: unknown): LiveIcpVersion[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    number: typeof r.number === 'number' ? r.number : (() => { throw new MapError('missing required field: number'); })(),
    contentHash: str(r, 'content_hash'),
    status: str(r, 'status'),
    approvedAt: typeof r.approved_at === 'string' ? r.approved_at : null,
  }));
}

export function toBuyers(data: unknown): LiveBuyer[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    name: str(r, 'name'),
    note: typeof r.note === 'string' ? r.note : null,
  }));
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs`
Expected: `14 live adapter checks passed`.

- [ ] **Step 5: Commit**

```bash
git add services/live/mapping.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): strict read-model mapping"
```

---

### Task 3: The live client — envelope, bearer, abort

**Files:**
- Create: `services/live/client.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `LiveError` (with `code`, `message`, `requestId`, `retryable`, `status`), `LiveCancelled`, `createLiveClient(fetchImpl?)` returning `{request<T>({path, method?, token?, scope, signal?}): Promise<T>}`.
- Consumes: nothing from earlier tasks except the checks harness. The client does not import `mapping.ts` or `mode.ts`.

**Design note:** the client takes an injected `fetchImpl` (defaulting to global `fetch`) so the checks never touch the network.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const live=await loadModule('services/live/client.ts');

function responder(handler){return async (url,init)=>{await handler(url,init);return {status:200,ok:true,json:async()=>({data:{ok:true},request_id:'r-1',data_mode:'live'})};};}
function errorResponder(status,body){return async ()=>({status,ok:false,json:async()=>body});}

await test('a success unwraps data and sends the bearer only when a token is present',async()=>{
  const seen=[];
  const client=live.createLiveClient(responder((url,init)=>seen.push(init.headers)));
  const out=await client.request({path:'/v1/workspaces',scope:'s1',token:'tok-1'});
  assert.deepEqual(out,{ok:true});
  assert.equal(seen[0].Authorization,'Bearer tok-1');
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[1].Authorization,undefined);
});

await test('an error envelope becomes a typed LiveError keyed by code',async()=>{
  const client=live.createLiveClient(errorResponder(503,{code:'PROVIDER_UNAVAILABLE',message:'down',request_id:'r-9',retryable:true}));
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>{
    assert.ok(e instanceof live.LiveError);
    assert.equal(e.code,'PROVIDER_UNAVAILABLE');
    assert.equal(e.status,503);
    assert.equal(e.retryable,true);
    assert.equal(e.requestId,'r-9');
    return true;
  });
});

await test('a non-envelope body still yields a typed error, never a crash',async()=>{
  const client=live.createLiveClient(errorResponder(500,'<html>oops</html>'));// json() will throw
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>e instanceof live.LiveError&&e.status===500);
});

await test('an aborted request surfaces as LiveCancelled, not as an error toast',async()=>{
  const client=live.createLiveClient(async()=>{const e=new Error('aborted');e.name='AbortError';throw e;});
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>e instanceof live.LiveCancelled);
});

await test('a network failure is a retryable error, not a cancellation',async()=>{
  // read.ts classifies on retryable/status, so this branch must be pinned, not merely implemented.
  const client=live.createLiveClient(async()=>{throw new TypeError('failed to fetch');});
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>{
    assert.ok(e instanceof live.LiveError);
    assert.equal(e.code,'NETWORK_ERROR');
    assert.equal(e.status,0);
    assert.equal(e.retryable,true);
    return true;
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/client.ts`.

- [ ] **Step 3: Implement `services/live/client.ts`**

```ts
export class LiveError extends Error {
  constructor(message: string, readonly code: string, readonly status: number, readonly requestId: string, readonly retryable: boolean) {
    super(message);
  }
}

/** A request was aborted because the scope changed. Normal, never an error state. */
export class LiveCancelled extends Error {}

export interface LiveRequest {
  path: string;
  method?: string;
  token?: string;
  scope: string;
  signal?: AbortSignal;
}

async function bodyOf(response: {json: () => Promise<unknown>}): Promise<Record<string, unknown>> {
  try {
    const parsed = await response.json();
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export function createLiveClient(fetchImpl: typeof fetch = fetch, baseUrl: string = '') {
  const root = baseUrl.replace(/\/+$/, '');
  return {
    async request<T>({path, method = 'GET', token, scope, signal}: LiveRequest): Promise<T> {
      void scope;
      const headers: Record<string, string> = {Accept: 'application/json'};
      if (token) headers.Authorization = `Bearer ${token}`;
      let response: Awaited<ReturnType<typeof fetch>>;
      try {
        // Without the configured base URL a live read would hit the app's own origin.
        response = await fetchImpl(`${root}${path}`, {method, headers, signal});
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') throw new LiveCancelled('cancelled');
        throw new LiveError('request failed', 'NETWORK_ERROR', 0, '', true);
      }
      if (!response.ok) {
        const body = await bodyOf(response as unknown as {json: () => Promise<unknown>});
        const code = typeof body.code === 'string' ? body.code : 'UNKNOWN_ERROR';
        const message = typeof body.message === 'string' ? body.message : 'request failed';
        const requestId = typeof body.request_id === 'string' ? body.request_id : '';
        throw new LiveError(message, code, response.status, requestId, body.retryable === true);
      }
      const body = await bodyOf(response as unknown as {json: () => Promise<unknown>});
      return (body as {data?: T}).data as T;
    },
  };
}

export type LiveClient = ReturnType<typeof createLiveClient>;
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs`
Expected: `19 live adapter checks passed`.

- [ ] **Step 5: Commit**

```bash
git add services/live/client.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): typed client with envelope, bearer and abort handling"
```

---

### Task 4: Session scope — abort, late-response discard, in-memory token

**Files:**
- Create: `services/live/session.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Produces: `interface Scope { mode: DataMode; actor: string; workspace: string | null; project: string | null }`; `scopeKey(scope: Scope): string`; `class SessionScope` with `current(): Scope`, `identity(): string`, `next(partial: Partial<Scope>): {scope: Scope; identity: string; previous: AbortController | undefined; controller: AbortController}`, `isCurrent(identity: string): boolean`, `controller(): AbortController`, `token(): string | undefined`, `setToken(t: string | undefined): void`.
- Consumes: `DataMode` type from `services/live/mode.ts` (Task 1).

**Why identity is a generation, not just a value.** A value key (`mode:actor:workspace:project`) is identical when a user returns to the same workspace, so an in-flight response from the *previous* visit to that workspace would still look current — the precise stale-response hazard the scope exists to prevent. `identity()` therefore prefixes a monotonic counter that `next()` increments on every scope change, so a return to a previously visited scope is a new generation and old responses are discarded. This is checked by the A to B to A case in Step 1.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const {SessionScope,scopeKey}=await loadModule('services/live/session.ts');

await test('scopeKey encodes mode, actor, workspace and project',()=>{
  assert.equal(scopeKey({mode:'live',actor:'a',workspace:'w',project:'p'}),'live:a:w:p');
  assert.equal(scopeKey({mode:'demo',actor:'',workspace:null,project:null}),'demo::-:-');
});

await test('changing workspace advances the identity and aborts the previous controller',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const first=session.next({workspace:'w1'});
  assert.equal(first.previous.signal.aborted,true);
  assert.equal(session.isCurrent(first.identity),true);
  const second=session.next({workspace:'w2'});
  assert.equal(second.previous,first.controller);
  assert.equal(second.previous.signal.aborted,true);
  assert.equal(session.isCurrent(first.identity),false);
});

await test('a stale identity is not current, so a late response can be discarded',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const stale=session.next({workspace:'w1'}).identity;
  session.next({workspace:'w2'});
  assert.equal(session.isCurrent(stale),false);
});

await test('returning to a previously visited workspace is a NEW scope, not the old one',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const firstA=session.next({workspace:'A'}).identity;
  session.next({workspace:'B'});
  const secondA=session.next({workspace:'A'}).identity;
  // Same value key, different generation: the earlier visit's response must not be accepted.
  assert.equal(scopeKey(session.current()),'live:a:A:-');
  assert.notEqual(firstA,secondA);
  assert.equal(session.isCurrent(firstA),false);
  assert.equal(session.isCurrent(secondA),true);
});

await test('the token lives in the session and survives a scope change',()=>{
  // The token identifies the actor, not the scope: switching workspace must not force
  // re-authentication. `next()` therefore keeps it; only an explicit setToken clears it.
  const session=new SessionScope({mode:'live',actor:'a'});
  session.setToken('tok');
  assert.equal(session.token(),'tok');
  session.next({workspace:'w2'});
  assert.equal(session.token(),'tok');
  session.setToken(undefined);
  assert.equal(session.token(),undefined);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/session.ts`.

- [ ] **Step 3: Implement `services/live/session.ts`**

```ts
import type {DataMode} from './mode';

export interface Scope { mode: DataMode; actor: string; workspace: string | null; project: string | null; }

export function scopeKey(scope: Scope): string {
  return `${scope.mode}:${scope.actor}:${scope.workspace ?? '-'}:${scope.project ?? '-'}`;
}

/**
 * Owns the current scope, the abort controller for its in-flight work, and the in-memory
 * token. Nothing here touches storage: the token never leaves the process.
 */
export class SessionScope {
  private scope: Scope;
  private generation = 0;
  // Named `currentController`, not `controller`: a field and a method of the same name are a
  // duplicate identifier in TypeScript, and at runtime the field shadowed the method so
  // `session.controller()` threw only once something called it.
  private currentController: AbortController;
  private currentToken: string | undefined;

  constructor(initial: {mode: DataMode; actor?: string; workspace?: string | null; project?: string | null}) {
    this.scope = {mode: initial.mode, actor: initial.actor ?? '', workspace: initial.workspace ?? null, project: initial.project ?? null};
    this.currentController = new AbortController();
  }

  current(): Scope {
    return {...this.scope};
  }

  /**
   * The identity of the current scope. The generation counter is what makes returning to a
   * previously visited workspace a *new* scope, so a response from the earlier visit is stale.
   */
  identity(): string {
    return `${this.generation}:${scopeKey(this.scope)}`;
  }

  /** Advance the scope, aborting the previous controller so stale work is cancelled. */
  next(partial: Partial<Scope>): {scope: Scope; identity: string; previous: AbortController | undefined; controller: AbortController} {
    const previous = this.currentController;
    previous?.abort();
    this.scope = {...this.scope, ...partial};
    this.generation += 1;
    this.currentController = new AbortController();
    return {scope: this.current(), identity: this.identity(), previous, controller: this.currentController};
  }

  /** True only for the newest scope; a late response with a stale identity is discarded. */
  isCurrent(identity: string): boolean {
    return identity === this.identity();
  }

  /** The signal for the current scope. A read attaches to this; only a scope change aborts it. */
  controller(): AbortController {
    return this.currentController;
  }

  token(): string | undefined {
    return this.currentToken;
  }

  setToken(token: string | undefined): void {
    this.currentToken = token;
  }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs`
Expected: `24 live adapter checks passed`.

- [ ] **Step 5: Commit**

```bash
git add services/live/session.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): session scope with abort and late-response discard"
```

---

### Task 5: Acceptance checks — isolation, tenant switch, storage hygiene

**Files:**
- Create: `services/live/read.ts`
- Modify: `tests/live-adapter-checks.mjs`
- Modify: `services/live/session.ts` (defect fix: rename the shadowing field — see below)

**Interfaces:**
- Produces: `loadLive({client, session, section, path, store?}): Promise<{availability: Availability; value?: unknown; error?: LiveError; discarded?: boolean}>` — the single place a live read is attempted, so the "never fall back to demo" rule has exactly one implementation and one test.
- Consumes: `client.ts` (Task 3), `session.ts` (Task 4), `mode.ts` (Task 1).

**Carried defect from Task 4 (fix here).** `services/live/session.ts` declared a private field `controller` *and* a method `controller()`. That is a duplicate identifier (`tsc` TS2300), and at runtime the field shadowed the method, so `session.controller()` threw — invisible to Task 4's checks because none of them called it. Rename the field to `currentController` throughout (constructor, `next()`, `controller()`). The Task 4 checks must stay green unchanged; this is the corrected Task 4 source.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const {loadLive}=await loadModule('services/live/read.ts');

function fakeStore(){return {touched:false,get companies(){this.touched=true;throw new Error('demo store consulted');}};}
function authed(){const s=new SessionScope({mode:'live',actor:'a'});s.setToken('tok');s.next({workspace:'w1'});return s;}

await test('live failure surfaces the error with zero data and never touches the demo store',async()=>{
  const store=fakeStore();
  const client=live.createLiveClient(errorResponder(503,{code:'PROVIDER_UNAVAILABLE',message:'down',request_id:'r',retryable:true}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store});
  assert.equal(result.value,undefined);
  assert.equal(store.touched,false);
  assert.equal(result.error.code,'PROVIDER_UNAVAILABLE');
  assert.equal(result.availability,'transient');
});

await test('a 501 from a supported section marks it unavailable rather than failing',async()=>{
  // section 'overview' IS live-supported, so the 501 must come from the response, not from availability.
  const client=live.createLiveClient(errorResponder(501,{code:'NOT_IMPLEMENTED',message:'no',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'unavailable');
  assert.equal(result.value,undefined);
});

await test('a section with no backing operation is unavailable without a request',async()=>{
  let calls=0;
  const client={request:async()=>{calls++;return {};}};
  const result=await loadLive({client,session:authed(),section:'discovery',path:'/v1/x',store:fakeStore()});
  assert.equal(result.availability,'unavailable');
  assert.equal(calls,0);
});

await test('a response whose scope changed underneath is discarded',async()=>{
  const session=authed();
  let release;const gate=new Promise(r=>{release=r;});
  const client={request:async()=>{await gate;return {items:[{id:'b-1',name:'A',note:null}]};}};
  const pending=loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  session.next({workspace:'B'});
  release();
  const result=await pending;
  assert.equal(result.value,undefined);
  assert.equal(result.discarded,true);
});

await test('no token means not_configured and no request is sent',async()=>{
  let calls=0;
  const client={request:async()=>{calls++;return {};}};
  const session=new SessionScope({mode:'live',actor:'a'});
  session.next({workspace:'w1'});
  const result=await loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'not_configured');
  assert.equal(calls,0);
});

await test('each API failure code maps to its own state',async()=>{
  const cases=[[401,'UNAUTHENTICATED','denied'],[403,'PERMISSION_DENIED','denied'],[404,'NOT_FOUND','not_found'],[503,'PROVIDER_UNAVAILABLE','transient'],[501,'NOT_IMPLEMENTED','unavailable']];
  for(const [status,code,expected] of cases){
    const client=live.createLiveClient(errorResponder(status,{code,message:'m',request_id:'r',retryable:status===503}));
    const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
    assert.equal(result.availability,expected,code);
    assert.equal(result.value,undefined,code);
  }
});

await test('a 404 is not_found, never denied',async()=>{
  // §C keeps "not found" distinct from "refused": a non-enumerating 404 for a foreign
  // resource must not render as a permission denial.
  const client=live.createLiveClient(errorResponder(404,{code:'NOT_FOUND',message:'m',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'not_found');
  assert.notEqual(result.availability,'denied');
});

await test('a 401 is a sign-in requirement, never not_configured',async()=>{
  // not_configured means "live is off and no request was made"; a 401 means a token was rejected.
  const client=live.createLiveClient(errorResponder(401,{code:'UNAUTHENTICATED',message:'m',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'denied');
  assert.notEqual(result.availability,'not_configured');
});

await test('a cancelled request is discarded, not an error',async()=>{
  const client=live.createLiveClient(async()=>{const e=new Error('aborted');e.name='AbortError';throw e;});
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.discarded,true);
  assert.equal(result.error,undefined);
});

await test('the read attaches to the session controller signal',async()=>{
  let seen;
  const client={request:async(args)=>{seen=args.signal;return {items:[]};}};
  const session=authed();
  await loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(seen,session.controller().signal);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/read.ts`.

- [ ] **Step 3: Implement `services/live/read.ts`**

```ts
import {availabilityFor, type Availability, type Section} from './mode';
import {LiveCancelled, type LiveError, type LiveClient} from './client';
import type {SessionScope} from './session';

export interface LoadResult {
  availability: Availability;
  value?: unknown;
  error?: LiveError;
  discarded?: boolean;
}

/**
 * The single entry point for a live read. Guarantees, in one place:
 *  - an unavailable/denied/error result never carries data;
 *  - a stale response is discarded, not applied;
 *  - the demo store is never consulted.
 */
export async function loadLive(input: {
  client: Pick<LiveClient, 'request'>;
  session: SessionScope;
  section: Section;
  path: string;
  store?: unknown;
}): Promise<LoadResult> {
  void input.store;
  const {client, session, section, path} = input;
  const scope = session.current();
  const availability = availabilityFor(scope.mode, section);
  if (availability !== 'available') return {availability};

  // Live requires a caller identity. With none, report it honestly rather than sending a
  // request that can only come back 401.
  const token = session.token();
  if (scope.mode === 'live' && !token) return {availability: 'not_configured'};

  const identity = session.identity();
  try {
    const value = await client.request({path, scope: identity, token, signal: session.controller().signal});
    if (!session.isCurrent(identity)) return {availability, discarded: true};
    return {availability, value};
  } catch (err) {
    if (err instanceof LiveCancelled) return {availability, discarded: true};
    const error = err as LiveError;
    if (error.code === 'NOT_IMPLEMENTED') return {availability: 'unavailable', error};
    // A received 401 means a token was presented and rejected: sign-in is required. It is NOT
    // `not_configured`, which is reserved for "live is off and no request was made".
    if (error.code === 'UNAUTHENTICATED' || error.code === 'PERMISSION_DENIED') return {availability: 'denied', error};
    if (error.code === 'NOT_FOUND') return {availability: 'not_found', error};
    if (error.retryable || error.status === 429 || error.status >= 500) return {availability: 'transient', error};
    return {availability: 'denied', error};
  }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node tests/live-adapter-checks.mjs`
Expected: `34 live adapter checks passed`.

- [ ] **Step 5: Commit**

```bash
git add services/live/read.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): single read path enforcing isolation and tenant-switch safety"
```

---

### Task 6: Providers, live panels and the mode-aware http-client

**Files:**
- Create: `services/live/storage.ts`
- Create: `features/providers/data-mode.tsx`
- Create: `features/providers/workspace-session.tsx`
- Create: `features/live/unavailable.tsx`
- Create: `features/live/overview.tsx`
- Modify: `services/http-client.ts`
- Modify: `tests/live-adapter-checks.mjs`
- Modify: `app/layout.tsx`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: `DataModeProvider({mode, apiBaseUrl, children})`, `useDataMode()`, `WorkspaceSessionProvider({children})`, `useWorkspaceSession()`, `LiveUnavailable({state, reason})`, `LiveOverview()`, and `services/http-client.ts` re-exporting `createLiveClient` alongside the existing demo helpers.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const storage=await loadModule('services/live/storage.ts');

await test('live mode refuses to read or write any demo storage key',()=>{
  const calls=[];
  const fake={getItem:k=>{calls.push('get:'+k);return null;},setItem:(k)=>{calls.push('set:'+k);}};
  storage.readDemoState(fake,'live');
  storage.writePrefs(fake,'live',{locale:'en'});
  assert.deepEqual(calls,[]);
});

await test('demo mode still reads and writes its own keys',()=>{
  const calls=[];
  const fake={getItem:k=>{calls.push('get:'+k);return null;},setItem:(k)=>{calls.push('set:'+k);}};
  storage.readDemoState(fake,'demo');
  storage.writePrefs(fake,'demo',{locale:'zh-HK'});
  assert.ok(calls.some(c=>c==='get:buyeros-demo-v1'));
  assert.ok(calls.some(c=>c==='set:buyeros-prefs-v1'));
});

await test('live requests are addressed to the configured API base URL',async()=>{
  // Without this the live path would silently call the app's own origin.
  const seen=[];
  const client=live.createLiveClient(async(url)=>{seen.push(String(url));return {ok:true,json:async()=>({data:{},request_id:'r',data_mode:'live'})};},'https://api.example.test/');
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[0],'https://api.example.test/v1/workspaces');
});

await test('with no base URL the path is used as-is',async()=>{
  const seen=[];
  const client=live.createLiveClient(async(url)=>{seen.push(String(url));return {ok:true,json:async()=>({data:{},request_id:'r',data_mode:'live'})};});
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[0],'/v1/workspaces');
});

await test('no token-shaped value is ever written to storage',()=>{
  const written=[];
  const fake={getItem:()=>null,setItem:(k,v)=>{written.push([k,String(v)]);}};
  storage.writePrefs(fake,'demo',{locale:'en'});
  assert.equal(written.some(([,v])=>/bearer|eyJ|token/i.test(v)),false);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/storage.ts`.

- [ ] **Step 3: Implement `services/live/storage.ts`, the providers and the panels**

```ts
// services/live/storage.ts
import type {DataMode} from './mode';

export const DEMO_KEYS = ['buyeros-demo-v1', 'buyeros-drafts-v1', 'buyeros-prefs-v1'] as const;

interface StorageLike { getItem(key: string): string | null; setItem(key: string, value: string): void; }

/** Live mode must never read or write a demo key. Demo mode is unchanged. */
export function readDemoState(storage: StorageLike, mode: DataMode): Record<string, unknown> {
  if (mode !== 'demo') return {};
  const out: Record<string, unknown> = {};
  for (const key of DEMO_KEYS) {
    const raw = storage.getItem(key);
    if (raw) out[key] = raw;
  }
  return out;
}

export function writePrefs(storage: StorageLike, mode: DataMode, prefs: {locale: string}): void {
  if (mode !== 'demo') return;
  storage.setItem('buyeros-prefs-v1', JSON.stringify({locale: prefs.locale}));
}
```

`features/providers/data-mode.tsx`:

```tsx
'use client';
import {createContext, useContext, type ReactNode} from 'react';
import type {DataMode} from '@/services/live/mode';

interface DataModeValue { mode: DataMode; apiBaseUrl: string; }
const DataModeContext = createContext<DataModeValue>({mode: 'demo', apiBaseUrl: ''});

export function DataModeProvider({mode, apiBaseUrl, children}: DataModeValue & {children: ReactNode}) {
  return <DataModeContext.Provider value={{mode, apiBaseUrl}}>{children}</DataModeContext.Provider>;
}

export function useDataMode(): DataModeValue {
  return useContext(DataModeContext);
}
```

`features/providers/workspace-session.tsx`:

```tsx
'use client';
import {createContext, useContext, useMemo, useRef, type ReactNode} from 'react';
import {SessionScope} from '@/services/live/session';
import {createLiveClient} from '@/services/live/client';
import {useDataMode} from './data-mode';

interface SessionValue { session: SessionScope; client: ReturnType<typeof createLiveClient>; }
const SessionContext = createContext<SessionValue | null>(null);

export function WorkspaceSessionProvider({children}: {children: ReactNode}) {
  const {mode, apiBaseUrl} = useDataMode();
  // Lazy `useState` is the lint-clean "construct exactly once" pattern. A `useRef` written
  // during render and read back through `useMemo` trips `react-hooks/refs` (an error here).
  const [value] = useState<SessionValue>(() => {
    const session = new SessionScope({mode, actor: ''});
    session.next({});
    return {session, client: createLiveClient(fetch, apiBaseUrl)};
  });
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useWorkspaceSession(): SessionValue {
  const value = useContext(SessionContext);
  if (value === null) throw new Error('useWorkspaceSession requires WorkspaceSessionProvider');
  return value;
}
```

`features/live/unavailable.tsx`:

```tsx
'use client';
import type {Availability} from '@/services/live/mode';

const COPY: Record<Exclude<Availability, 'available'>, string> = {
  unavailable: 'Not available in live mode yet.',
  not_configured: 'Live mode is not configured. Showing nothing rather than sample data.',
  denied: 'Access denied for this workspace.',
  transient: 'The service is temporarily unavailable. Retry when ready.',
  not_found: 'Not found in this workspace.',
};

export function LiveUnavailable({state, reason}: {state: Exclude<Availability, 'available'>; reason?: string}) {
  return (
    <section className="panel" role="status">
      <p>{COPY[state]}</p>
      {reason ? <small>{reason}</small> : null}
    </section>
  );
}
```

`features/live/overview.tsx` — renders the live workspace/project context from `useWorkspaceSession()`, calling `loadLive` for `/v1/workspaces`, and rendering `LiveUnavailable` for any non-`available` outcome. No demo import.

`services/http-client.ts` becomes:

```ts
export {httpClient} from './mock-client';
export {createLiveClient, LiveError, LiveCancelled} from './live/client';
```

`app/layout.tsx` resolves mode server-side and wraps the shell:

```tsx
import {resolveMode} from '@/services/live/mode';
...
const apiBaseUrl = process.env.BUYEROS_API_BASE_URL ?? '';
// Use the tested resolver rather than re-deriving the rule inline.
const mode = resolveMode(apiBaseUrl);
...
<body className="antialiased">
  <DataModeProvider mode={mode} apiBaseUrl={apiBaseUrl}>
    <WorkspaceSessionProvider>
      <Workspace mode={mode} />
    </WorkspaceSessionProvider>
  </DataModeProvider>
</body>
```

**The env mechanism (confirmed during Task 6, was NOT RUN in the plan).** `process.env` **is** reachable from the server component — the built `dist/server/index.js` keeps the runtime lookup — but it is populated from the **Cloudflare Worker `vars`/bindings**, not from the launching shell: a shell-level `BUYEROS_API_BASE_URL` left the mode at `demo`, while adding it to the built `dist/server/wrangler.json` `vars` flipped the mode to `live` with no rebuild. The repository therefore has **no in-repo source** for this variable; it must be set as a Worker `var` at deploy time. That is the intended "configuration change, not a code change" switch described in §B.

- [ ] **Step 4: Run the checks and the existing suites**

Run: `node tests/live-adapter-checks.mjs` → Expected: `39 live adapter checks passed`.
Run: `node tests/domain-checks.mjs` → Expected: `11 domain checks passed`.
Run: `pnpm lint` → Expected: PASS (no new warnings).

- [ ] **Step 5: Commit**

```bash
git add services/live/storage.ts features/providers features/live services/http-client.ts app/layout.tsx tests/live-adapter-checks.mjs
git commit -m "feat(live): providers, live panels and mode-aware http client"
```

---

### Task 7: Workspace wiring, isolation and the mode banner

**Files:**
- Modify: `features/workspace.tsx`
- Modify: `locales/index.ts`
- Modify: `tests/live-adapter-checks.mjs`

**Interfaces:**
- Consumes: `useDataMode` (Task 6), `useWorkspaceSession` (Task 6), `readDemoState`/`writePrefs` (Task 6), `LiveOverview` (Task 6).
- Produces: a workspace that accepts `mode: DataMode`, gates every demo-only effect, and branches its section blocks on mode.

- [ ] **Step 1: Write the failing checks**

Append to `tests/live-adapter-checks.mjs` (before the final `console.log`):

```js
const ws=await loadModule('services/live/workspace-logic.ts');

await test('demo-only effects are enabled only in demo mode',()=>{
  assert.equal(ws.demoEffectsEnabled('demo'),true);
  assert.equal(ws.demoEffectsEnabled('live'),false);
});

await test('the empty live store contains no companies and no demo identifiers',()=>{
  const s=ws.emptyStore();
  assert.deepEqual(s.companies,[]);
  assert.equal(s.budget,0);
  assert.equal(s.locale,'en');
});

await test('the banner label states the real mode and cannot be made to claim live',()=>{
  // Pin the leading mode word: the demo banner legitimately mentions "live" in
  // "No live services connected", so a substring test would be meaningless.
  assert.match(ws.modeBanner('demo'),/^demo mode\b/i);
  assert.match(ws.modeBanner('live'),/^live mode\b/i);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/live-adapter-checks.mjs`
Expected: FAIL — `Cannot find module .../services/live/workspace-logic.ts`.

- [ ] **Step 3: Implement `services/live/workspace-logic.ts`**

```ts
import type {DataMode} from './mode';
import type {Store} from '@/services/contracts';

/** Demo-only effects (storage restore, preference writes, the run timer, WebMCP) run in demo only. */
export function demoEffectsEnabled(mode: DataMode): boolean {
  return mode === 'demo';
}

/** A live session has no demo store: empty data, never fictional data. */
export function emptyStore(): Store {
  return {
    companies: [], lists: [], drafts: [], quotes: [], costs: [], outcomes: [], runs: [],
    budget: 0, discoveryBudget: 0, contactUnitPrice: 0, locale: 'en', defaultMarkets: '',
  };
}

export function modeBanner(mode: DataMode): string {
  return mode === 'live' ? 'Live mode · connected workspace' : 'Demo mode · No live services connected';
}
```

- [ ] **Step 4: Wire `features/workspace.tsx` (four targeted edits)**

1. Signature and store initialisation (line 27): accept `mode` and pick the initial store from it.

```tsx
export default function Workspace({mode='demo'}:{mode?:DataMode}){const [s,setS]=useState<Store>(()=>mode==='demo'?seed():emptyStore()),[loaded,L]=useState(false);
```

2. Gate the demo-only effects. Wrap the bodies of the WebMCP effect (line 29), the demo storage restore (line 32), the preferences write (line 33) and the run timer (line 37) in `if(!demoEffectsEnabled(mode))return;` as their first statement. Gate the unconditional `usage(s)` computation (line 38) so `u` is computed only in demo mode, and give it a zero-valued fallback in live mode.

3. Branch the render: wrap the existing section blocks (lines 52-59) in `{mode==='demo'&&(<>…</>)}`, and add a sibling `{mode==='live'&&<LiveOverview/>}` for the overview route with `LiveUnavailable` for the other routes based on `availabilityFor(mode,'discovery')` etc. The demo branch keeps its current contents verbatim.
   Two implementation details this needs, neither of which is obvious from the snippet:
   - **Guard the derived `rows`/`run` values.** Line 39 derives from `s.runs`, and live mode's `emptyStore()` has `runs: []`, so `run.id` throws. Guard the derived values (e.g. a `rows` that tolerates no run) so the live branch renders without a run — the checks' demo path must stay byte-identical.
   - **Add `mode` to the dependency arrays** of the effects you gate, otherwise `react-hooks/exhaustive-deps` reports new warnings against a file that already has pre-existing lint errors.

4. Banner: replace the hard-coded demo banner text with `t(modeBanner(mode))` so it always states the resolved mode.

Add the needed imports at the top: `import {type DataMode} from '@/services/live/mode';`, `import {demoEffectsEnabled,emptyStore,modeBanner} from '@/services/live/workspace-logic';`, `import {LiveOverview} from './live/overview';`, `import {LiveUnavailable} from './live/unavailable';`.

- [ ] **Step 5: Add the new labels to `locales/index.ts`**

Append the zh-HK strings for the new English labels: `Live mode · connected workspace`, `Not available in live mode yet.`, `Live mode is not configured. Showing nothing rather than sample data.`, `Access denied for this workspace.`

- [ ] **Step 6: Run everything**

Run: `node tests/live-adapter-checks.mjs` → Expected: `42 live adapter checks passed`.
Run: `node tests/domain-checks.mjs` → Expected: `11 domain checks passed`.
Run: `pnpm lint` → Expected: PASS.
Run: `pnpm build` → Expected: PASS (the app still builds under vinext).

Record the demo-unchanged evidence: in demo mode the app still renders 24 fixture companies (open the app or assert through `seed()`).

- [ ] **Step 7: Commit**

```bash
git add features/workspace.tsx services/live/workspace-logic.ts locales/index.ts tests/live-adapter-checks.mjs
git commit -m "feat(live): wire the workspace seam and label unavailable sections"
```

---

## Self-Review

- **Spec coverage:** §A boundaries (Tasks 1-6 create exactly the named units, plus the two pure modules the refinement note explains); §B mode resolution and adapter contract (Tasks 1, 3); §C read models and availability (Tasks 2, 5); §D workspace wiring and isolation (Tasks 6, 7); §E errors, abort and tenant-switch safety (Tasks 3, 4, 5); §F testing and acceptance mapping (Task 5 covers 01/02/03, Task 7 adds storage and banner checks); §G out of scope (no task, by design). Every section maps to a task.
- **Acceptance mapping:** TEST-BO-006-01 → Task 5's "live failure yields unavailable/error with zero data and never touches the demo store" plus Task 7's demo-unchanged evidence; TEST-BO-006-02 → Task 4's scope tests and Task 5's "response whose scope changed is discarded"; TEST-BO-006-03 → Task 6's storage checks and Task 7's WebMCP gating.
- **Placeholder scan:** no `TBD`/`TODO`; every code step contains complete code. The one deliberately deferred item — confirming `process.env` reaches server code — is marked NOT RUN with a named fallback, not left vague.
- **Type consistency:** `DataMode`, `Availability`, `Section` (Task 1) are used unchanged by Tasks 4-7. `LiveError`/`LiveCancelled` (Task 3) are consumed by Task 5. `SessionScope`/`scopeKey` (Task 4) are consumed by Tasks 5-6. `Store`/`seed`/`base` keep their existing P2-era shapes.
- **Known limitation carried forward:** the checks are node scripts and cannot render React. Every seam decision is a pure function covered by a check; `features/live/*`, the providers and the `workspace.tsx` branch are thin renderers over them. DOM assertions are out of scope (spec §F).

## Global Notes

- No remote commits/pushes, deploys, cloud resources, real-data migrations, provider calls, or sends.
- Record exact command output in `PROGRESS.md`; every unexecuted check is **NOT RUN**.
- Execution requires a recorded dependency waiver and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
