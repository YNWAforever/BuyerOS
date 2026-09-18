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

/** A required string. A missing, empty or non-string value raises, never becomes ''. */
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
