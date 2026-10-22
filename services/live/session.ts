import {LiveCancelled} from './client';
import type {DataMode} from './mode';

export interface Scope { mode: DataMode; actor: string; workspace: string | null; project: string | null; }
export interface ScopeSnapshot {scope: Scope; identity: string; authenticated: boolean;}
export interface WriteContext {identity: string; actor: string; workspace: string; project: string | null; signal: AbortSignal;}
export function scopeKey(scope: Scope): string {
  return `${scope.mode}:${scope.actor}:${scope.workspace ?? '-'}:${scope.project ?? '-'}`;
}

/** In-memory token and scope. A generation, rather than a scope key, rejects A-B-A late results. */
export class SessionScope {
  private scope: Scope;
  private generation = 0;
  private currentController = new AbortController();
  private currentToken: string | undefined;
  private listeners = new Set<() => void>();
  private clearListeners = new Set<() => void>();
  private transitionGuards = new Set<(proceed: () => Promise<void>) => Promise<boolean>>();
  private transitionPredicates = new Map<(proceed:()=>Promise<void>)=>Promise<boolean>,()=>boolean>();
  private transitioning = false;
  private clearedPreparationEdits = false;
  private snapshot: ScopeSnapshot;

  constructor(initial: {mode: DataMode; actor?: string; workspace?: string | null; project?: string | null}) {
    this.scope = {mode: initial.mode, actor: initial.actor ?? '', workspace: initial.workspace ?? null, project: initial.project ?? null};
    this.snapshot = {scope: {...this.scope}, identity: this.identity(), authenticated: false};
  }
  private publish(): void {
    this.snapshot = {scope: {...this.scope}, identity: this.identity(), authenticated: !!this.currentToken && !!this.scope.actor};
    for (const listener of this.listeners) listener();
  }
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  subscribeBeforeClear(listener: () => void): () => void {
    this.clearListeners.add(listener); return () => {this.clearListeners.delete(listener);};
  }
  registerTransitionGuard(handler: (proceed: () => Promise<void>) => Promise<boolean>,blocking:()=>boolean=()=>true): () => void {
    this.transitionGuards.add(handler);this.transitionPredicates.set(handler,blocking);
    return () => {this.transitionGuards.delete(handler);this.transitionPredicates.delete(handler);};
  }
  hasBlockingTransitionGuards():boolean {
    for(const blocking of this.transitionPredicates.values()){try{if(blocking())return true;}catch{return true;}}
    return false;
  }
  hasTransitionGuards():boolean {return this.transitionGuards.size>0;}
  async transition(proceed: () => Promise<void>): Promise<boolean> {
    if (this.transitioning) return false;
    const identity = this.identity(); this.transitioning = true;
    const guarded = async () => {if (!this.isCurrent(identity)) throw new LiveCancelled('scope changed'); await proceed();};
    try {
      // Every mounted editor must consent before the actual navigation. A later
      // cancellation may leave an earlier save complete, never a partial navigation.
      for (const handler of [...this.transitionGuards]) {
        if (!await handler(async()=>{if(!this.isCurrent(identity))throw new LiveCancelled('scope changed');})) return false;
      }
      await guarded(); return true;
    }
    finally {this.transitioning = false;}
  }
  // Generic, in-memory notice only. Never retain preparation text or scope IDs.
  markPreparationEditsCleared(): void { this.clearedPreparationEdits = true; }
  preparationEditsWereCleared(): boolean { return this.clearedPreparationEdits; }
  getSnapshot = (): ScopeSnapshot => this.snapshot;
  current(): Scope { return {...this.scope}; }
  identity(): string { return `${this.generation}:${scopeKey(this.scope)}`; }
  next(partial: Partial<Scope>): {scope: Scope; identity: string; previous: AbortController; controller: AbortController} {
    const previous = this.currentController;
    previous.abort();
    this.scope = {...this.scope, ...partial};
    this.generation++;
    this.currentController = new AbortController();
    this.publish();
    return {scope: this.current(), identity: this.identity(), previous, controller: this.currentController};
  }
  isCurrent(identity: string): boolean { return identity === this.identity(); }
  controller(): AbortController { return this.currentController; }
  token(): string | undefined { return this.currentToken; }
  setToken(token: string | undefined): void {
    if (this.currentToken === token) return;
    if (!token) for (const listener of this.clearListeners) {try {listener();} catch {/* Security clearing cannot be prevented by a buffer/storage failure. */}}
    this.currentToken = token;
    if (token) this.clearedPreparationEdits = false;
    if (!token) this.next({actor: '', workspace: null, project: null});
    else this.publish();
  }
  captureWriteContext(): WriteContext {
    if (this.scope.mode !== 'live' || !this.currentToken || !this.scope.actor || !this.scope.workspace) throw new Error('Authenticated workspace required');
    return {identity: this.identity(), actor: this.scope.actor, workspace: this.scope.workspace, project: this.scope.project, signal: this.currentController.signal};
  }
}
