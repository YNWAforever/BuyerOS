/**
 * Monotonic thread readback.
 *
 * A GET thread is a complete authorized snapshot, not a patch. Reads must be
 * applied in observation order and the route/request they were issued for must
 * still be current. A late older read must never erase newer data or regress the
 * version used for the next `If-Match`; an equal or newer read is authoritative
 * even when it contains less data because permissions can change independently
 * of the thread version.
 */
import type {ChatThread} from './types';

const savedThreadIdPattern=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
/** Route ids are exact saved UUIDs; anything else is never navigated to. */
export function isSavedThreadId(value:unknown):value is string{
  return typeof value==='string'&&savedThreadIdPattern.test(value);
}
/** True when the next read is an older observation of the same thread. */
export function staleReadback(previous:ChatThread|null,next:ChatThread):boolean{
  return previous!==null&&previous.id===next.id&&next.version<previous.version;
}
/**
 * A full readback replaces the loaded snapshot only when it is for the same
 * thread and not older. Equal versions are accepted: a later authorized read may
 * drop messages, sources or runs the caller can no longer see.
 */
export function mergeReadback(previous:ChatThread|null,next:ChatThread):ChatThread{
  if(!previous||previous.id!==next.id)return next;
  return next.version<previous.version?previous:next;
}
