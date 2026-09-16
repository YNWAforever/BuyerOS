import {availabilityFor, type Availability, type Section} from './mode';
import {LiveCancelled, type LiveError, type LiveClient} from './client';
import type {SessionScope} from './session';

export interface LoadResult {
  availability: Availability;
  value?: unknown;
  error?: LiveError;
  discarded?: boolean;
}

/**
 * The single entry point for a live read. Guarantees, in one place:
 *  - an unavailable/denied/error result never carries data;
 *  - a stale response is discarded, not applied;
 *  - the demo store is never consulted.
 */
export async function loadLive(input: {
  client: Pick<LiveClient, 'request'>;
  session: SessionScope;
  section: Section;
  path: string;
  store?: unknown;
}): Promise<LoadResult> {
  void input.store;
  const {client, session, section, path} = input;
  const scope = session.current();
  const availability = availabilityFor(scope.mode, section);
  if (availability !== 'available') return {availability};

  // Live requires a caller identity. With none, report it honestly rather than sending a
  // request that can only come back 401.
  const token = session.token();
  if (scope.mode === 'live' && !token) return {availability: 'not_configured'};

  const identity = session.identity();
  try {
    const value = await client.request({path, scope: identity, token, signal: session.controller().signal});
    if (!session.isCurrent(identity)) return {availability, discarded: true};
    return {availability, value};
  } catch (err) {
    if (err instanceof LiveCancelled) return {availability, discarded: true};
    const error = err as LiveError;
    if (error.code === 'NOT_IMPLEMENTED') return {availability: 'unavailable', error};
    // A received 401 means a token was presented and rejected: sign-in is required. It is NOT
    // `not_configured`, which is reserved for "live is off and no request was made".
    if (error.code === 'UNAUTHENTICATED' || error.code === 'PERMISSION_DENIED') return {availability: 'denied', error};
    if (error.code === 'NOT_FOUND') return {availability: 'not_found', error};
    if (error.retryable || error.status === 429 || error.status >= 500) return {availability: 'transient', error};
    return {availability: 'denied', error};
  }
}
