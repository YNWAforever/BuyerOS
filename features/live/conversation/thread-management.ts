/**
 * Thread management (increment 2.5) pure model: personal pin/archive preferences
 * and the share-control ACL. The backend stores preferences per viewer; these
 * helpers keep the other preference flag intact and keep UI state honest.
 */
export type ThreadAccess='owner'|'editor'|'viewer';
export type PreferenceChange='pin'|'archive';
export type ThreadPreferences={pinned:boolean;archived:boolean};

/** Toggle one preference; the other flag is always preserved verbatim. */
export function nextThreadPreferences(current:ThreadPreferences,change:PreferenceChange):ThreadPreferences{
  return change==='pin'?{pinned:!current.pinned,archived:current.archived}
    :{pinned:current.pinned,archived:!current.archived};
}
/** Personal view preference: every access role may set its own pin/archive state. */
export function preferenceAllowed(access:ThreadAccess):boolean{
  return access==='owner'||access==='editor'||access==='viewer';
}
/** Share reads/writes are owner-only; viewers and editors never get the dialog. */
export function shareControlVisible(access:ThreadAccess):boolean{
  return access==='owner';
}
export function sortThreadRows<T extends {pinned?:boolean;updatedAt:number}>(items:ReadonlyArray<T>):T[]{
  return [...items].sort((left,right)=>Number(right.pinned??false)-Number(left.pinned??false)||right.updatedAt-left.updatedAt);
}
/** The archive view lists archived rows; the normal list hides them. */
export function visibleThreadRows<T extends {archived?:boolean}>(items:ReadonlyArray<T>,archivedView:boolean):T[]{
  return items.filter(row=>archivedView||!row.archived);
}
function normalizePreference(stored:unknown,payload:ThreadPreferences):ThreadPreferences{
  const row=typeof stored==='object'&&stored!==null?stored as Record<string,unknown>:{};
  return {
    pinned:typeof row.pinned==='boolean'?row.pinned:payload.pinned,
    archived:typeof row.archived==='boolean'?row.archived:payload.archived,
  };
}
/** Persist the toggled preference and return the server's stored projection. */
export async function persistThreadPreference(
  api:{preferences:(id:string,pinned:boolean,archived:boolean)=>Promise<unknown>},
  id:string,current:ThreadPreferences,change:PreferenceChange,
):Promise<{payload:ThreadPreferences;stored:ThreadPreferences}>{
  const payload=nextThreadPreferences(current,change);
  const stored=normalizePreference(await api.preferences(id,payload.pinned,payload.archived),payload);
  return {payload,stored};
}
/** Apply only a persisted server result; a failed request never changes the row. */
export function applyStoredPreference<T extends {pinned?:boolean;archived?:boolean}>(row:T,stored:Partial<ThreadPreferences>|null|undefined):T{
  return {...row,pinned:typeof stored?.pinned==='boolean'?stored.pinned:row.pinned===true,
    archived:typeof stored?.archived==='boolean'?stored.archived:row.archived===true};
}
export function applyStoredListPreference<T extends {id:string;pinned?:boolean;archived?:boolean}>(
  items:ReadonlyArray<T>,id:string,stored:Partial<ThreadPreferences>|null|undefined,
):T[]{
  return items.map(row=>row.id===id?applyStoredPreference(row,stored):row);
}
