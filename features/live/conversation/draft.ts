/**
 * Unsent composer text, persisted per actor + workspace + project + thread.
 *
 * The persisted object also carries the `client_message_id` that a failed or
 * uncertain send must reuse. Editing the text after a failure mints a new id, so
 * an exact-once retry can never carry different content under the same id.
 * Dependency-free and storage-injectable for node:test.
 */
export type DraftStorage=Pick<Storage,'getItem'|'setItem'|'removeItem'>;
export type DraftScope={actor:string;workspace:string;project:string};
export type ConversationDraft={text:string;clientMessageId:string;boundText:string;updatedAt:number};
export const draftVersion=1;
export const draftMaxText=4_000;
export const draftMaxBytes=16*1024;
const uuidRe=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
export function isThreadDraftKey(value:unknown):value is string{
  return value==='new'||(typeof value==='string'&&uuidRe.test(value));
}
export function draftKey(scope:DraftScope,threadKey:string):string{
  return `buyeros.conversation.draft.v${draftVersion}:${encodeURIComponent(scope.actor)}:${encodeURIComponent(scope.workspace)}:${encodeURIComponent(scope.project)}:${encodeURIComponent(threadKey)}`;
}
export function newClientMessageId():string{
  return crypto.randomUUID();
}
function isRecord(value:unknown):value is Record<string,unknown>{
  return typeof value==='object'&&value!==null&&!Array.isArray(value);
}
export function readDraftValue(raw:unknown):ConversationDraft|null{
  if(typeof raw!=='string'||raw.length===0||raw.length>draftMaxBytes)return null;
  let value:unknown;try{value=JSON.parse(raw);}catch{return null;}
  if(!isRecord(value)||value.version!==draftVersion)return null;
  if(typeof value.text!=='string'||value.text.length===0||value.text.trim().length===0||value.text.length>draftMaxText)return null;
  if(typeof value.clientMessageId!=='string'||!uuidRe.test(value.clientMessageId))return null;
  if(typeof value.boundText!=='string'||value.boundText.length>draftMaxText||value.boundText!==value.text)return null;
  if(!Number.isSafeInteger(value.updatedAt)||(value.updatedAt as number)<0)return null;
  return {text:value.text,clientMessageId:value.clientMessageId,boundText:value.boundText,updatedAt:value.updatedAt as number};
}
/** Pure transition: keep the id only while the attempt text is unchanged. */
export function nextDraft(previous:ConversationDraft|null,text:string,now:number,newId:()=>string=newClientMessageId):ConversationDraft|null{
  if(typeof text!=='string'||text.trim().length===0||text.length>draftMaxText)return null;
  if(previous&&previous.boundText===text)return {...previous,updatedAt:now};
  return {text,clientMessageId:newId(),boundText:text,updatedAt:now};
}
export function draftPayload(draft:ConversationDraft):string{
  const bounded={version:draftVersion,text:draft.text,clientMessageId:draft.clientMessageId,boundText:draft.boundText,updatedAt:draft.updatedAt};
  const payload=JSON.stringify(bounded);
  if(payload.length>draftMaxBytes)throw new Error('draft too large');
  return payload;
}
function validScope(scope:DraftScope):boolean{
  return [scope.actor,scope.workspace,scope.project].every(part=>typeof part==='string'&&part.length>0&&part.length<=255);
}
/** Storage failures degrade to this tab only; the draft is never silently written elsewhere. */
export class ConversationDrafts{
  private memory=new Map<string,string>();
  private persistent=true;
  constructor(private scope:DraftScope,private storage?:DraftStorage){
    if(!validScope(scope))this.persistent=false;
    if(!storage){
      try{this.storage=typeof window==='undefined'?undefined:window.localStorage;}catch{this.storage=undefined;}
    }
    if(!this.storage)this.persistent=false;
  }
  get available():boolean{return this.persistent;}
  read(threadKey:string):ConversationDraft|null{
    if(!validScope(this.scope))return null;
    const key=draftKey(this.scope,threadKey);
    const raw=this.memory.get(key)??this.readStorage(key);
    return readDraftValue(raw);
  }
  write(threadKey:string,text:string,now=Date.now()):ConversationDraft|null{
    if(!validScope(this.scope))return null;
    const draft=nextDraft(this.read(threadKey),text,now);
    const key=draftKey(this.scope,threadKey);
    if(!draft){this.memory.delete(key);this.removeStorage(key);return null;}
    let payload:string;try{payload=draftPayload(draft);}catch{return null;}
    this.memory.set(key,payload);
    try{this.storage?.setItem(key,payload);this.persistent=true;}
    catch{this.persistent=false;}
    return draft;
  }
  clear(threadKey:string):void{
    const key=draftKey(this.scope,threadKey);
    this.memory.delete(key);this.removeStorage(key);
  }
  private readStorage(key:string):string|null{
    if(!this.storage)return null;
    try{return this.storage.getItem(key);}catch{this.persistent=false;return null;}
  }
  private removeStorage(key:string):void{
    if(!this.storage)return;
    try{this.storage.removeItem(key);}catch{this.persistent=false;}
  }
}
