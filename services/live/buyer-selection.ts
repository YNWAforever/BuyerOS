/** Build the contract `Selection` for a review action. No UI, no storage, no demo data. */

export interface VersionedBuyer { id: string; version: number; }
export type ReviewSelection =
  | { kind: 'explicit'; buyers: VersionedBuyer[] }
  | { kind: 'snapshot'; snapshot_id: string; excluded_ids: string[] };

export function explicitSelection(buyers: VersionedBuyer[]): ReviewSelection {
  return { kind: 'explicit', buyers };
}

export function snapshotSelection(snapshotId: string, excludedIds: string[]): ReviewSelection {
  return { kind: 'snapshot', snapshot_id: snapshotId, excluded_ids: excludedIds };
}
