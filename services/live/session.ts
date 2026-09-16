import type {DataMode} from './mode';

export interface Scope { mode: DataMode; actor: string; workspace: string | null; project: string | null; }

export function scopeKey(scope: Scope): string {
  return `${scope.mode}:${scope.actor}:${scope.workspace ?? '-'}:${scope.project ?? '-'}`;
}

/**
 * Owns the current scope, the abort controller for its in-flight work, and the in-memory
 * token. Nothing here touches storage: the token never leaves the process.
 */
export class SessionScope {
  private scope: Scope;
  private generation = 0;
  private controller: AbortController | undefined;
  private currentToken: string | undefined;

  constructor(initial: {mode: DataMode; actor?: string; workspace?: string | null; project?: string | null}) {
    this.scope = {mode: initial.mode, actor: initial.actor ?? '', workspace: initial.workspace ?? null, project: initial.project ?? null};
    this.controller = new AbortController();
  }

  current(): Scope {
    return {...this.scope};
  }

  /**
   * The identity of the current scope. The generation counter is what makes returning to a
   * previously visited workspace a *new* scope, so a response from the earlier visit is stale.
   */
  identity(): string {
    return `${this.generation}:${scopeKey(this.scope)}`;
  }

  /** Advance the scope, aborting the previous controller so stale work is cancelled. */
  next(partial: Partial<Scope>): {scope: Scope; identity: string; previous: AbortController | undefined; controller: AbortController} {
    const previous = this.controller;
    previous?.abort();
    this.scope = {...this.scope, ...partial};
    this.generation += 1;
    this.controller = new AbortController();
    return {scope: this.current(), identity: this.identity(), previous, controller: this.controller};
  }

  /** True only for the newest scope; a late response with a stale identity is discarded. */
  isCurrent(identity: string): boolean {
    return identity === this.identity();
  }

  /** The signal for the current scope. A read attaches to this; only a scope change aborts it. */
  controller(): AbortController {
    return this.controller!;
  }

  token(): string | undefined {
    return this.currentToken;
  }

  setToken(token: string | undefined): void {
    this.currentToken = token;
  }
}
