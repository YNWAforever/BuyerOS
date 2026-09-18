export type DataMode = 'demo' | 'live';
/** unavailable = no backing operation; not_configured = no identity; denied = refused;
 *  transient = retryable (429/503/network). Never inferred from empty data. */
export type Availability = 'available' | 'unavailable' | 'not_configured' | 'denied' | 'transient' | 'not_found';
export type Section = 'overview' | 'discovery' | 'lists' | 'outreach' | 'results' | 'settings';

/** Sections the live API can back in this phase. Everything else is explicitly unavailable. */
export const LIVE_SECTIONS: Section[] = ['overview', 'settings'];

export function resolveMode(apiBaseUrl?: string | null): DataMode {
  return apiBaseUrl && apiBaseUrl.trim() ? 'live' : 'demo';
}

export function availabilityFor(mode: DataMode, section: Section, liveReady: boolean = true): Availability {
  if (mode === 'demo') return 'available';
  if (!LIVE_SECTIONS.includes(section)) return 'unavailable';
  return liveReady ? 'available' : 'not_configured';
}
