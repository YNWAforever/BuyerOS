/**
 * Explicit notes only: a turn route that is genuinely absent may fall back to the
 * saved-note path (the composer exposes that action explicitly). A turn route that
 * is merely unavailable (outage, timeout, failed probe) never converts a typed
 * message into a note; the draft stays with the person and Send reports the outage.
 */
import type {TurnCapability} from './types';

export const sendNotices={
  outage:'Conversation replies are unavailable right now. Your text is kept here; nothing was sent.',
  checking:'Replies are still being checked. Your text is kept here.',
  absentSend:'Continuous replies are not available here. Your message was not sent; choose Save as note to keep it.',
  unresolved:'A previous message may not have been saved. Retry it to check the saved result before sending new text.',
  recoveredSaved:'The earlier message was already saved. Nothing was sent twice; your current draft is still here.',
  recoveredSent:'The earlier message was sent once. Your current draft is still here.',
} as const;

export type SendIntent='send'|'note';
export type SendDisposition={kind:'turn'}|{kind:'note'}|{kind:'blocked';notice:string};
/**
 * Click intent is authoritative. A normal Send that waits on a capability probe
 * never becomes a note when the probe later reports the notes-only surface.
 */
export function sendDisposition(capability:TurnCapability,intent:SendIntent):SendDisposition{
  if(intent==='note')return {kind:'note'};
  if(capability==='available')return {kind:'turn'};
  if(capability==='absent')return {kind:'blocked',notice:sendNotices.absentSend};
  return {kind:'blocked',notice:capability==='checking'?sendNotices.checking:sendNotices.outage};
}
