'use client';
import type {Availability} from '@/services/live/mode';

const COPY: Record<Exclude<Availability, 'available'>, string> = {
  unavailable: 'Not available in live mode yet.',
  not_configured: 'Live mode is not configured. Showing nothing rather than sample data.',
  denied: 'Access denied for this workspace.',
  transient: 'The service is temporarily unavailable. Retry when ready.',
  not_found: 'Not found in this workspace.',
};

export function LiveUnavailable({state, reason}: {state: Exclude<Availability, 'available'>; reason?: string}) {
  return (
    <section className="panel" role="status">
      <p>{COPY[state]}</p>
      {reason ? <small>{reason}</small> : null}
    </section>
  );
}
