import {LiveCancelled} from './client';
import type {SessionScope} from './session';
import type {WriteContext} from './operations';

/** Token, epoch and destination are captured together, never borrowed from a later account. */
export function leadContext(session:SessionScope,signal?:AbortSignal):WriteContext&{project:string}{
  const captured=session.captureWriteContext(),token=session.token();
  if(!captured.project||!token)throw new Error('Select an authenticated project first.');
  return {...captured,project:captured.project,
    signal:signal?AbortSignal.any([captured.signal,signal]):captured.signal,
    getToken:async()=>{if(!session.isCurrent(captured.identity))throw new LiveCancelled('scope changed');return token;},
    isCurrent:()=>session.isCurrent(captured.identity)};
}
