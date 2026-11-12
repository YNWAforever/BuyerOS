/**
 * Render window for the conversation transcript.
 *
 * The server caps a discussion at 100 notes (`MESSAGE_LIMIT`), so the data is
 * already bounded; this window keeps the *rendered* persisted history bounded too
 * because each entry can mount rich parts, citations and proposals. The latest
 * WINDOW persisted entries render initially; every reveal adds exactly one BATCH
 * of older entries. Live/ephemeral entries are outside this window and always
 * render, so a streamed reply never hides or displaces revealed history.
 */
export const TRANSCRIPT_WINDOW=25;
export const TRANSCRIPT_BATCH=25;
export type TranscriptWindowState={
  /** Whether a non-empty persisted history has established the window. */
  initialized:boolean;
  /** First persisted entry index that is rendered. */
  start:number;
  /** Number of persisted entries the window currently describes. */
  total:number;
};
function normalize(total:number):number{
  return Number.isFinite(total)?Math.max(0,Math.floor(total)):0;
}
/** Latest bounded subset for the first persisted read. */
export function initialWindow(total:number):TranscriptWindowState{
  const bounded=normalize(total);
  return {initialized:bounded>0,start:Math.max(0,bounded-TRANSCRIPT_WINDOW),total:bounded};
}
/**
 * Reconcile a window with a changed persisted total. A growing total (a new turn
 * that is persisted, or another read) never moves the revealed start backwards,
 * so older entries the user already revealed stay mounted.
 */
export function receiveEntryTotal(state:TranscriptWindowState,total:number):TranscriptWindowState{
  const bounded=normalize(total);
  if(!state.initialized)return initialWindow(bounded);
  if(bounded===state.total)return state;
  return {...state,total:bounded,start:Math.min(state.start,Math.max(0,bounded))};
}
/** Reveal one older batch; the control's no-op state keeps the same object. */
export function revealEarlier(state:TranscriptWindowState):TranscriptWindowState{
  if(!state.initialized||state.start<=0)return state;
  return {...state,start:Math.max(0,state.start-TRANSCRIPT_BATCH)};
}
export function hasEarlier(state:TranscriptWindowState):boolean{
  return state.initialized&&state.start>0;
}
/** The visible slice of persisted entries; never longer than the total. */
export function windowSlice<T>(persisted:ReadonlyArray<T>,state:TranscriptWindowState):T[]{
  return persisted.slice(Math.min(state.start,persisted.length));
}
