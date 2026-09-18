import type {DataMode} from './mode';

export const DEMO_KEYS = ['buyeros-demo-v1', 'buyeros-drafts-v1', 'buyeros-prefs-v1'] as const;

interface StorageLike { getItem(key: string): string | null; setItem(key: string, value: string): void; }

/** Live mode must never read or write a demo key. Demo mode is unchanged. */
export function readDemoState(storage: StorageLike, mode: DataMode): Record<string, unknown> {
  if (mode !== 'demo') return {};
  const out: Record<string, unknown> = {};
  for (const key of DEMO_KEYS) {
    const raw = storage.getItem(key);
    if (raw) out[key] = raw;
  }
  return out;
}

export function writePrefs(storage: StorageLike, mode: DataMode, prefs: {locale: string}): void {
  if (mode !== 'demo') return;
  storage.setItem('buyeros-prefs-v1', JSON.stringify({locale: prefs.locale}));
}
