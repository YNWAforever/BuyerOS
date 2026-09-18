import type {DataMode} from './mode';
import type {Store} from '@/services/contracts';

/** Demo-only effects (storage restore, preference writes, the run timer, WebMCP) run in demo only. */
export function demoEffectsEnabled(mode: DataMode): boolean {
  return mode === 'demo';
}

/** A live session has no demo store: empty data, never fictional data. */
export function emptyStore(): Store {
  return {
    companies: [], lists: [], drafts: [], quotes: [], costs: [], outcomes: [], runs: [],
    budget: 0, discoveryBudget: 0, contactUnitPrice: 0, locale: 'en', defaultMarkets: '',
  };
}

export function modeBanner(mode: DataMode): string {
  return mode === 'live' ? 'Live mode · connected workspace' : 'Demo mode · No live services connected';
}
