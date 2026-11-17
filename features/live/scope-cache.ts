/**
 * Per-tab, per-identity cache of signed-in scope data so a reload paints the
 * workspace immediately while the authoritative reads revalidate in the
 * background. Only values the signed-in user already sees are retained
 * (identifiers, display names, roles, status); nothing is shared between
 * identities and the cache lives in sessionStorage, so closing the tab clears it.
 */

export interface ScopeWorkspace {id: string; name: string; roles: string[]; membershipId: string | null}
export interface ScopeProject {id: string; name: string; status: string}

type Bucket = {workspaces?: ScopeWorkspace[]; projects?: Record<string, ScopeProject[]>};
type Store = {version: 1; identities: Record<string, Bucket>};

const KEY = 'buyeros.scope-cache.v1';
const MAX_IDENTITIES = 4;
const MAX_WORKSPACES = 25;
const MAX_PROJECTS = 50;

function storage(): Storage | null {
  try {return typeof window === 'undefined' ? null : window.sessionStorage;} catch {return null;}
}

function readStore(): Store | null {
  const area = storage();
  if (!area) return null;
  try {
    const parsed: unknown = JSON.parse(area.getItem(KEY) ?? 'null');
    if (!parsed || typeof parsed !== 'object') return null;
    const store = parsed as Partial<Store>;
    if (store.version !== 1 || !store.identities || typeof store.identities !== 'object') return null;
    return store as Store;
  } catch {return null;}
}

function writeStore(store: Store): void {
  const area = storage();
  if (!area) return;
  try {area.setItem(KEY, JSON.stringify(store));} catch {/* Cache is optional; the live read still wins. */}
}

function storeForWrite(): Store {
  return readStore() ?? {version: 1, identities: {}};
}

function bucketFor(store: Store, identity: string, create: boolean): Bucket | null {
  const existing = store.identities[identity];
  if (existing) return existing;
  if (!create) return null;
  const identities = Object.keys(store.identities);
  if (identities.length >= MAX_IDENTITIES) delete store.identities[identities[0]];
  const bucket: Bucket = {};
  store.identities[identity] = bucket;
  return bucket;
}

function normalizeWorkspaces(value: unknown): ScopeWorkspace[] | null {
  if (!Array.isArray(value) || value.length > MAX_WORKSPACES) return null;
  const rows = value.map(item => {
    if (!item || typeof item !== 'object') return null;
    const row = item as Record<string, unknown>;
    const id = typeof row.id === 'string' ? row.id : null;
    const name = typeof row.name === 'string' ? row.name : null;
    if (!id || !name) return null;
    return {
      id, name,
      roles: Array.isArray(row.roles) ? row.roles.filter((role): role is string => typeof role === 'string') : [],
      membershipId: typeof row.membershipId === 'string' ? row.membershipId : null,
    };
  });
  return rows.every((row): row is ScopeWorkspace => row !== null) ? rows : null;
}

function normalizeProjects(value: unknown): ScopeProject[] | null {
  if (!Array.isArray(value) || value.length > MAX_PROJECTS) return null;
  const rows = value.map(item => {
    if (!item || typeof item !== 'object') return null;
    const row = item as Record<string, unknown>;
    const id = typeof row.id === 'string' ? row.id : null;
    const name = typeof row.name === 'string' ? row.name : null;
    const status = typeof row.status === 'string' ? row.status : null;
    return id && name && status ? {id, name, status} : null;
  });
  return rows.every((row): row is ScopeProject => row !== null) ? rows : null;
}

export function cachedWorkspaces(identity: string): ScopeWorkspace[] | null {
  if (!identity) return null;
  const store = readStore();
  const bucket = store ? bucketFor(store, identity, false) : null;
  if (!bucket) return null;
  const rows = normalizeWorkspaces(bucket.workspaces);
  return rows && rows.length ? rows : null;
}

export function rememberWorkspaces(identity: string, items: readonly ScopeWorkspace[]): void {
  const store = storeForWrite();
  const bucket = bucketFor(store, identity, true);
  if (!bucket) return;
  bucket.workspaces = items.slice(0, MAX_WORKSPACES).map(item => ({
    id: item.id, name: item.name, roles: [...item.roles], membershipId: item.membershipId ?? null,
  }));
  writeStore(store);
}

export function cachedProjects(identity: string, workspace: string): ScopeProject[] | null {
  if (!identity || !workspace) return null;
  const store = readStore();
  const bucket = store ? bucketFor(store, identity, false) : null;
  if (!bucket) return null;
  const rows = normalizeProjects(bucket.projects?.[workspace]);
  return rows && rows.length ? rows : null;
}

export function rememberProjects(identity: string, workspace: string, items: readonly ScopeProject[]): void {
  if (!identity || !workspace) return;
  const store = storeForWrite();
  const bucket = bucketFor(store, identity, true);
  if (!bucket) return;
  bucket.projects = bucket.projects ?? {};
  const keys = Object.keys(bucket.projects);
  if (keys.length >= MAX_WORKSPACES) delete bucket.projects[keys[0]];
  bucket.projects[workspace] = items.slice(0, MAX_PROJECTS).map(item => ({id: item.id, name: item.name, status: item.status}));
  writeStore(store);
}

/** Project display name already observed for this scope, so the transcript avoids a second read. */
export function cachedProjectName(identity: string, workspace: string, project: string): string | null {
  if (!identity || !workspace || !project) return null;
  const store = readStore();
  const bucket = store ? bucketFor(store, identity, false) : null;
  const row = bucket?.projects?.[workspace]?.find(item => item.id === project);
  return row && typeof row.name === 'string' && row.name.length <= 200 ? row.name : null;
}

export function clearScopeCache(): void {
  const area = storage();
  if (!area) return;
  try {area.removeItem(KEY);} catch {/* Cache is optional. */}
}
