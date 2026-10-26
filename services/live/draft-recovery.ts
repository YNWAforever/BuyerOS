export interface RetainedDraft {
  actor: string; workspace: string; project: string; draftId: string; revisionId: string;
  version: number; subject: string; body: string; language: 'en' | 'zh-HK';
}
type StoragePort = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
const key = 'buyeros-private-draft-recovery';
const same = (a: RetainedDraft, b: Pick<RetainedDraft, 'actor' | 'workspace' | 'project' | 'draftId'>) =>
  a.actor === b.actor && a.workspace === b.workspace && a.project === b.project && a.draftId === b.draftId;
function valid(value: unknown): value is RetainedDraft {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  return Object.keys(v).sort().join(',') === 'actor,body,draftId,language,project,revisionId,subject,version,workspace'
    && ['actor','workspace','project','draftId','revisionId'].every(k => typeof v[k] === 'string' && !!v[k] && (v[k] as string).length <= 255)
    && typeof v.subject === 'string' && typeof v.body === 'string' && (v.subject.length + v.body.length) <= 250_000
    && Number.isSafeInteger(v.version) && (v.version as number) > 0 && ['en','zh-HK'].includes(v.language as string);
}
/** Per-tab recovery contains text only, never auth tokens, intents or grants. The UI calls
 * find only after reauthentication and a successful scoped server read, then compares versions.
 * Storage failure retains the in-memory copy; it never prevents security invalidation.
 */
export class DraftRecovery {
  private buffers: RetainedDraft[] = [];
  constructor(private storage?: StoragePort) {
    try {const raw = storage?.getItem(key); if (!raw || raw.length > 1_000_000) return;
      const parsed: unknown = JSON.parse(raw); if (Array.isArray(parsed) && parsed.length <= 64) this.buffers = parsed.filter(valid);
    } catch {/* Never render unvalidated stored data. */}
  }
  private save(): boolean {
    if (!this.storage) return false;
    try {const payload=JSON.stringify(this.buffers);if(this.buffers.length>64||payload.length>1_000_000)return false;if (this.buffers.length) this.storage.setItem(key,payload); else this.storage.removeItem(key); return true;}
    catch {return false;}
  }
  retain(value: RetainedDraft): boolean {
    if (!valid(value)) throw new Error('Invalid draft recovery buffer');
    const existing = this.buffers.findIndex(row => same(row, value));
    if (existing < 0) this.buffers.push({...value}); else this.buffers[existing] = {...value};
    return this.save();
  }
  hasRetained(): boolean { return this.buffers.length > 0; }
  find(scope: Pick<RetainedDraft, 'actor' | 'workspace' | 'project' | 'draftId'>): RetainedDraft | null {
    const value = this.buffers.find(row => same(row, scope)); return value ? {...value} : null;
  }
  forget(scope: Pick<RetainedDraft, 'actor' | 'workspace' | 'project' | 'draftId'>): void {this.buffers = this.buffers.filter(row => !same(row, scope)); this.save();}
}
