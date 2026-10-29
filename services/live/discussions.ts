'use client';
import {validRunReference,type RunReference} from './conversation-research';
import {exactFields,validGroundedReply,type GroundedReply} from './discussion-citations';

export type DiscussionScope = {actor: string; workspace: string; project: string};
export type SelectedSource = {id: string; label: string};
export type LocalThread = {
  id: string; templateId: string; title: string; createdAt: number; updatedAt: number;
  messages: ({id: string; text: string} | ({id:string;kind:'ai'} & GroundedReply))[]; sources: SelectedSource[]; runs?: RunReference[];
};
export type DiscussionSnapshot = {threads: LocalThread[]; notice: string};

type StoragePort = Pick<Storage, 'getItem' | 'setItem'>;
const MAX_BYTES = 256 * 1024;
// Leave a millisecond below Date's inclusive maximum and refuse further increments.
const MAX_TIMESTAMP = 8_639_999_999_999_999;
const templates = new Set(['first-project', 'understand-documents', 'research-market',
  'review-buyers', 'check-company', 'prepare-follow-up', 'custom']);
const localId = /^local-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sourceLabels: Record<string, readonly string[]> = {
  document: ['Offer document'], fact: ['Offer fact', 'Approved offer fact', 'Candidate offer fact'],
  run: ['Research run'], results: ['Results summary'],
};
const memoryNotice = 'Local storage is unavailable. Discussions are kept only in this tab.';

/** Reject unknown fields, including non-enumerable fields and accessors on API inputs. */
function fields(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return false;
  const actual = Reflect.ownKeys(value);
  return actual.length === keys.length && actual.every(key => typeof key === 'string'
    && keys.includes(key) && 'value' in Object.getOwnPropertyDescriptor(value, key)!);
}
function validScope(value: unknown): value is DiscussionScope {
  return fields(value, ['actor', 'workspace', 'project'])
    && [value.actor, value.workspace, value.project].every(part => typeof part === 'string' && !!part.trim() && part.length <= 255);
}
function validText(value: unknown): value is string {
  return typeof value === 'string' && !!value.trim() && value.length <= 4000;
}
function validSource(value: unknown): value is SelectedSource {
  if (!fields(value, ['id', 'label']) || typeof value.id !== 'string' || value.id.length > 200
    || typeof value.label !== 'string' || value.label.length > 80) return false;
  const match = /^(document|fact|run|results):[A-Za-z0-9][A-Za-z0-9._:-]*$/.exec(value.id);
  return !!match && sourceLabels[match[1]].includes(value.label);
}
function validThread(value: unknown): value is LocalThread {
  if ((!fields(value, ['id', 'templateId', 'title', 'createdAt', 'updatedAt', 'messages', 'sources'])
      && !fields(value, ['id', 'templateId', 'title', 'createdAt', 'updatedAt', 'messages', 'sources', 'runs']))
    || typeof value.id !== 'string' || !localId.test(value.id)
    || typeof value.templateId !== 'string' || !templates.has(value.templateId)
    || typeof value.title !== 'string' || !value.title.trim() || value.title.length > 80
    || !Number.isSafeInteger(value.createdAt) || (value.createdAt as number) < 0 || (value.createdAt as number) > MAX_TIMESTAMP
    || !Number.isSafeInteger(value.updatedAt) || (value.updatedAt as number) < (value.createdAt as number)
    || (value.updatedAt as number) > MAX_TIMESTAMP
    || !Array.isArray(value.messages) || !value.messages.length || value.messages.length > 100
    || !Array.isArray(value.sources) || value.sources.length > 100
    || (value.runs!==undefined&&(!Array.isArray(value.runs)||value.runs.length>100||!value.runs.every(validRunReference)||new Set(value.runs.map(row=>row.id)).size!==value.runs.length))) return false;
  const messageIds = new Set<string>(), sourceIds = new Set<string>();
  return value.messages.every(message => {
    const ai=exactFields(message,['id','kind','status','text','citations','fixture'])&&message.kind==='ai'&&message.fixture===true&&
      validGroundedReply({status:message.status,text:message.text,citations:message.citations,fixture:message.fixture});
    if ((!fields(message, ['id', 'text'])&&!ai) || typeof message.id !== 'string' || !localId.test(message.id)
      || !validText(message.text) || messageIds.has(message.id)) return false;
    messageIds.add(message.id); return true;
  }) && value.sources.every(source => {
    if (!validSource(source) || sourceIds.has(source.id)) return false;
    sourceIds.add(source.id); return true;
  });
}
function byteLength(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}
function freezeSnapshot(snapshot: DiscussionSnapshot): DiscussionSnapshot {
  for (const thread of snapshot.threads) {
    thread.messages.forEach(message=>{
      if('kind' in message){message.citations.forEach(ref=>{Object.freeze(ref.locator);Object.freeze(ref);});Object.freeze(message.citations);}
      Object.freeze(message);
    });
    thread.runs?.forEach(Object.freeze);if(thread.runs)Object.freeze(thread.runs);
    thread.sources.forEach(Object.freeze);
    Object.freeze(thread.messages); Object.freeze(thread.sources); Object.freeze(thread);
  }
  Object.freeze(snapshot.threads); Object.freeze(snapshot);
  return snapshot;
}
function newestFirst(threads: LocalThread[]): LocalThread[] {
  return threads.sort((a, b) => b.updatedAt - a.updatedAt || b.createdAt - a.createdAt || a.id.localeCompare(b.id));
}

/** Local user notes and source references only. This store never reads source bodies or calls a service. */
export class DiscussionStore {
  private active = false;
  private scope: DiscussionScope = {actor: '', workspace: '', project: ''};
  private key = '';
  private storage?: StoragePort;
  private savedRaw: string | null | undefined;
  private listeners = new Set<() => void>();
  private snapshot = freezeSnapshot({threads: [], notice: ''});

  constructor(enabled: boolean, scope: DiscussionScope, storage?: StoragePort) {
    if (!enabled) return;
    if (!validScope(scope)) {
      this.snapshot = freezeSnapshot({threads: [], notice: 'A valid account, workspace and project are required for local discussions.'});
      return;
    }
    this.active = true;
    this.scope = {...scope};
    this.key = `buyeros.discussions.v1:${encodeURIComponent(scope.actor)}:${encodeURIComponent(scope.workspace)}:${encodeURIComponent(scope.project)}`;
    try {
      this.storage = storage ?? (typeof window === 'undefined' ? undefined : window.localStorage);
      if (!this.storage) {
        this.snapshot = freezeSnapshot({threads: [], notice: memoryNotice});
        return;
      }
      const raw = this.storage.getItem(this.key);
      this.savedRaw = raw;
      if (raw === null) return;
      if (raw.length > MAX_BYTES || byteLength(raw) > MAX_BYTES) {
        this.ignore('Saved discussions exceeded the local storage limit and were ignored.'); return;
      }
      const saved: unknown = JSON.parse(raw);
      if (!fields(saved, ['version', 'scope', 'threads'])) {
        this.ignore('Saved discussions were invalid and were ignored.'); return;
      }
      if (saved.version !== 1) {
        this.ignore('Saved discussions use an unsupported version and were ignored.'); return;
      }
      if (!validScope(saved.scope) || saved.scope.actor !== scope.actor
        || saved.scope.workspace !== scope.workspace || saved.scope.project !== scope.project) {
        this.ignore('Saved discussions did not match this account, workspace and project and were ignored.'); return;
      }
      if (!Array.isArray(saved.threads) || saved.threads.length > 30 || !saved.threads.every(validThread)
        || new Set(saved.threads.map(thread => thread.id)).size !== saved.threads.length) {
        this.ignore('Saved discussions were invalid and were ignored.'); return;
      }
      this.snapshot = freezeSnapshot({threads: newestFirst(saved.threads), notice: ''});
    } catch {
      if (this.savedRaw === undefined) this.storage = undefined;
      this.ignore('Saved discussions could not be read and were ignored. New discussions are kept in this tab if storage is unavailable.');
    }
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  getSnapshot = (): DiscussionSnapshot => this.snapshot;

  /** Serialize browser read/check/write sequences across tabs. Recheck scope after waiting. */
  async withLocalWrite(isCurrent: () => boolean, write: () => void): Promise<void> {
    if (!this.active || !isCurrent()) return;
    const run = () => { if (isCurrent()) write(); };
    let entered = false;
    try {
      if (typeof navigator !== 'undefined' && navigator.locks) {
        await navigator.locks.request(this.key, () => { entered = true; run(); });
        return;
      }
    } catch (error) {
      if (entered) throw error;
    }
    // Without a cross-tab lock, keep edits in memory instead of risking saved work.
    this.storage = undefined;
    run();
  }

  private ignore(notice: string): void {
    this.snapshot = freezeSnapshot({threads: [], notice});
  }
  private publish(threads: LocalThread[], notice: string): void {
    this.snapshot = freezeSnapshot({threads, notice});
    this.listeners.forEach(listener => listener());
  }
  private refuse(notice: string): false {
    if (notice !== this.snapshot.notice) this.publish(this.snapshot.threads, notice);
    return false;
  }
  private nextTime(): number | null {
    const next = Math.max(Date.now(), ...this.snapshot.threads.map(thread => thread.updatedAt + 1));
    if (next > MAX_TIMESTAMP) {
      this.refuse('The local discussion timestamp limit has been reached. Existing discussions have been kept.');
      return null;
    }
    return next;
  }
  private save(threads: LocalThread[]): boolean {
    const ordered = newestFirst(threads);
    const payload = JSON.stringify({version: 1, scope: this.scope, threads: ordered});
    if (byteLength(payload) > MAX_BYTES) return this.refuse('The local discussion storage limit is full. Existing discussions have been kept.');
    let notice = '';
    if (!this.storage) notice = memoryNotice;
    else {
      try {
        if (this.savedRaw === undefined || this.storage.getItem(this.key) !== this.savedRaw)
          return this.refuse('Saved discussions changed in another tab. Changes were not saved. Copy any unsaved work before reloading.');
        this.storage.setItem(this.key, payload);
        this.savedRaw = payload;
      }
      catch { notice = 'Local storage could not save these changes. They are kept only in this tab.'; }
    }
    this.publish(ordered, notice);
    return true;
  }

  create(templateId: string, prompt: string): LocalThread | null {
    if (!this.active) return null;
    if (!templates.has(templateId) || !validText(prompt)) {
      this.refuse('Choose a discussion template and enter a question of up to 4,000 characters.'); return null;
    }
    if (this.snapshot.threads.length >= 30) {
      this.refuse('The local discussion limit of 30 threads is full. Existing discussions have been kept.'); return null;
    }
    const now = this.nextTime();
    if (now === null) return null;
    const thread: LocalThread = {
      id: `local-${globalThis.crypto.randomUUID()}`, templateId,
      title: prompt.trim().replace(/\s+/g, ' ').slice(0, 80), createdAt: now, updatedAt: now,
      messages: [{id: `local-${globalThis.crypto.randomUUID()}`, text: prompt}], sources: [],
    };
    return this.save([thread, ...this.snapshot.threads]) ? thread : null;
  }

  remove(id: string): boolean {
    if (!this.active || !this.snapshot.threads.some(row => row.id === id)) return false;
    return this.save(this.snapshot.threads.filter(row => row.id !== id));
  }

  append(id: string, text: string): boolean {
    if (!this.active) return false;
    const thread = this.snapshot.threads.find(row => row.id === id);
    if (!thread) return false;
    if (!validText(text)) return this.refuse('Enter a question of up to 4,000 characters.');
    if (thread.messages.length >= 100) return this.refuse('The local limit of 100 messages in this discussion is full. Existing messages have been kept.');
    const now = this.nextTime();
    if (now === null) return false;
    const updated: LocalThread = {...thread, updatedAt: now,
      messages: [...thread.messages, {id: `local-${globalThis.crypto.randomUUID()}`, text}]};
    return this.save(this.snapshot.threads.map(row => row.id === id ? updated : row));
  }

  select(id: string, source: SelectedSource, selected: boolean): boolean {
    if (!this.active) return false;
    const thread = this.snapshot.threads.find(row => row.id === id);
    if (!thread) return false;
    if (!validSource(source) || typeof selected !== 'boolean') return this.refuse('Only generic source labels and valid source references can be saved.');
    const existing = thread.sources.find(row => row.id === source.id);
    if (selected && existing?.label === source.label || !selected && !existing) return true;
    if (selected && !existing && thread.sources.length >= 100) return this.refuse('The local limit of 100 sources in this discussion is full. Existing sources have been kept.');
    const now = this.nextTime();
    if (now === null) return false;
    const sources = thread.sources.filter(row => row.id !== source.id);
    if (selected) sources.push({id: source.id, label: source.label});
    const updated: LocalThread = {...thread, updatedAt: now, sources};
    return this.save(this.snapshot.threads.map(row => row.id === id ? updated : row));
  }

  /** Save the question and verified fixture response together under the existing scope lock. */
  appendReply(id:string,text:string,reply:GroundedReply,sourceIds:string[]):boolean{
    if(!this.active)return false;
    const thread=this.snapshot.threads.find(row=>row.id===id);
    if(!thread||!validText(text)||!validGroundedReply(reply)||reply.fixture!==true||
      JSON.stringify(thread.sources.map(row=>row.id))!==JSON.stringify(sourceIds)||
      reply.citations.some(ref=>!sourceIds.includes(ref.id)))return false;
    if(thread.messages.length>98)return this.refuse('The local limit of 100 messages in this discussion is full. Existing messages have been kept.');
    const now=this.nextTime();if(now===null)return false;
    const ai={id:`local-${globalThis.crypto.randomUUID()}`,kind:'ai' as const,...reply,
      citations:reply.citations.map(ref=>({...ref,locator:{...ref.locator}}))};
    const updated:LocalThread={...thread,updatedAt:now,messages:[...thread.messages,{id:`local-${globalThis.crypto.randomUUID()}`,text},ai]};
    return this.save(this.snapshot.threads.map(row=>row.id===id?updated:row));
  }
  /** Financial result references only: strip every other server field before saving. */
  saveRun(id:string,run:RunReference):boolean{
    if(!this.active||!validRunReference(run))return false;
    const thread=this.snapshot.threads.find(row=>row.id===id);if(!thread)return false;
    const existing=thread.runs??[];
    if(existing.some(row=>row.id===run.id&&row.status===run.status))return true;
    if(!existing.some(row=>row.id===run.id)&&existing.length>=100)return this.refuse('The local run reference limit is full. Open Research runs.');
    const now=this.nextTime();if(now===null)return false;
    const ref:RunReference={id:run.id,label:'Research run',status:run.status};
    const runs=existing.some(row=>row.id===run.id)?existing.map(row=>row.id===run.id?ref:row):[...existing,ref];
    return this.save(this.snapshot.threads.map(row=>row.id===id?{...thread,updatedAt:now,runs}:row));
  }

}
