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
    this.currentToken = token;
    if (!token) this.next({actor: '', workspace: null, project: null});
    else this.publish();
  }
  captureWriteContext(): WriteContext {
    if (this.scope.mode !== 'live' || !this.currentToken || !this.scope.actor || !this.scope.workspace) throw new Error('Authenticated workspace required');
    return {identity: this.identity(), actor: this.scope.actor, workspace: this.scope.workspace, project: this.scope.project, signal: this.currentController.signal};
  }
}
