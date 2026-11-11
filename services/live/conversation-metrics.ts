/**
 * Read-only loader for the bounded turn-metrics endpoint (increment 3.6).
 *
 * Metrics are aggregate dashboard data: a failure never changes composer state
 * and never falls back to a guessed number. Scope changes cancel the read.
 */
import {LiveCancelled, LiveError, type LiveClient} from './client';
import type {SessionScope} from './session';
import {METRICS_WINDOW_DAYS, metricsPath, readTurnMetrics, type TurnMetrics} from
  '../../features/live/conversation/metrics';

export type MetricsLoadFailure = 'denied' | 'unavailable';

export class MetricsLoadError extends Error {
  constructor(readonly failure: MetricsLoadFailure) {
    super(failure === 'denied' ? 'Turn metrics are not available for this role.'
      : 'Turn metrics are unavailable. Try again later.');
  }
}

export async function loadTurnMetrics(client: LiveClient, session: SessionScope,
  windowDays = METRICS_WINDOW_DAYS): Promise<TurnMetrics> {
  if (!session.isCurrent(session.identity()) || !session.token()) throw new LiveCancelled('scope changed');
  const scope = session.current();
  if (scope.mode !== 'live' || !scope.workspace || !scope.project) throw new LiveCancelled('scope changed');
  const path = metricsPath(scope.workspace, scope.project, windowDays);
  if (!path) throw new MetricsLoadError('unavailable');
  try {
    const value = await client.request<unknown>({
      path, method: 'GET', token: session.token(), scope: session.identity(),
      signal: session.controller().signal,
    });
    return readTurnMetrics(value);
  } catch (error) {
    if (error instanceof LiveCancelled) throw error;
    const denied = error instanceof LiveError && (error.status === 401 || error.status === 403);
    throw new MetricsLoadError(denied ? 'denied' : 'unavailable');
  }
}
