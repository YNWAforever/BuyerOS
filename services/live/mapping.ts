export interface LiveWorkspace { id: string; name: string; roles: string[]; membershipId: string | null; }
export interface LiveProject { id: string; name: string; status: string; }
export interface LiveIcpVersion { id: string; number: number; contentHash: string; status: string; approvedAt: string | null; }
export interface LiveBuyer {
  id: string; name: string; version: number; fitVerdict: string | null; fitFreshness: string | null;
  reviewStatus: string | null; ownerMembershipId: string | null; note: string | null; evidenceCount: number;
  domain: string | null; contactResearchStatus: string | null;
  fitRationale: string | null; reviewReason: string | null; reviewAt: string | null;
}
export interface LiveBuyerPage { items: LiveBuyer[]; snapshotId: string; offset: number; limit: number; total: number; expiresAt: string | null; }
export interface LiveEvidence {
  id: string; relationship: string; excerpt: string; kind: string; status: string;
  sourceUrl: string | null; retrievedAt: string | null; observedAt: string | null;
  retentionUntil: string | null; originalLanguage: string | null; contentHash: string | null;
  requirementId: string | null; translatedExcerpt: string | null;
}

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
    membershipId: optionalString(r, 'membership_id'),
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

function num(row: Record<string, unknown>, key: string): number {
  const v = row[key];
  if (typeof v === 'number') return v;
  throw new MapError(`missing required field: ${key}`);
}

function optionalString(row: Record<string, unknown>, key: string): string | null {
  const v = row[key];
  return typeof v === 'string' ? v : null;
}

export function toBuyers(data: unknown): LiveBuyer[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    name: str(r, 'name'),
    version: num(r, 'version'),
    fitVerdict: typeof r.fit === 'object' && r.fit !== null ? optionalString(r.fit as Record<string, unknown>, 'verdict') : null,
    fitFreshness: typeof r.fit === 'object' && r.fit !== null ? optionalString(r.fit as Record<string, unknown>, 'freshness') : null,
    reviewStatus: typeof r.review === 'object' && r.review !== null ? optionalString(r.review as Record<string, unknown>, 'status') : null,
    ownerMembershipId: optionalString(r, 'owner_membership_id'),
    note: optionalString(r, 'note'),
    evidenceCount: num(r, 'evidence_count'),
    domain: optionalString(r,'normalized_domain'),
    contactResearchStatus: optionalString(r,'contact_research_status'),
    fitRationale: typeof r.fit === 'object' && r.fit !== null ? optionalString(r.fit as Record<string,unknown>,'rationale') : null,
    reviewReason: typeof r.review === 'object' && r.review !== null ? optionalString(r.review as Record<string,unknown>,'reason') : null,
    reviewAt: typeof r.review === 'object' && r.review !== null ? optionalString(r.review as Record<string,unknown>,'at') : null,
  }));
}

export function toBuyerPage(data: unknown): LiveBuyerPage {
  if (typeof data !== 'object' || data === null) throw new MapError('expected a buyer page object');
  const page = data as Record<string, unknown>;
  return {
    items: toBuyers(data),
    snapshotId: str(page, 'snapshot_id'),
    offset: num(page, 'offset'),
    limit: num(page, 'limit'),
    total: num(page, 'total'),
    expiresAt: optionalString(page, 'expires_at'),
  };
}

export function toEvidence(data: unknown): LiveEvidence[] {
  return rows(data).map((r) => ({
    id: str(r, 'id'),
    relationship: str(r, 'relationship'),
    excerpt: str(r, 'excerpt'),
    kind: str(r, 'kind'),
    status: str(r, 'status'),
    sourceUrl: r.status === 'available' ? optionalString(r, 'source_url') : null,
    retrievedAt: optionalString(r,'retrieved_at'),
    observedAt: optionalString(r,'observed_at'),
    retentionUntil: optionalString(r,'retention_until'),
    originalLanguage: optionalString(r,'original_language'),
    contentHash: optionalString(r,'content_hash'),
    requirementId: optionalString(r,'requirement_id'),
    translatedExcerpt: optionalString(r,'translated_excerpt'),
  }));
}

export function toEvidencePage(data: unknown): { items: LiveEvidence[]; total: number } {
  if (typeof data !== 'object' || data === null) throw new MapError('expected an evidence page object');
  return { items: toEvidence(data), total: num(data as Record<string, unknown>, 'total') };
}
