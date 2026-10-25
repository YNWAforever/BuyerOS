'use client';
import {useEffect} from 'react';
import type {Locale, PageId} from './content';
import {publicPath} from './routes';

export type MarketingEventName = 'cta_click' | 'locale_change' | 'demo_form_start' | 'demo_submit_success';
export function marketingEvent(name: MarketingEventName, locale: Locale, page: PageId, position: string) {
  // Local integration hook only. No cookies, storage, remote provider or form data.
  window.dispatchEvent(new CustomEvent('buyeros:marketing', {detail: {
    name, locale, path: publicPath(locale, page), position: position.slice(0, 40),
  }}));
}
export function MarketingEvents({locale, page}: {locale: Locale; page: PageId}) {
  useEffect(() => {
    const listener = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest<HTMLElement>('[data-marketing-event]');
      if (!link) return;
      const name = link.dataset.marketingEvent;
      if (name === 'cta_click' || name === 'locale_change') marketingEvent(name, locale, page, link.dataset.position ?? 'link');
    };
    document.addEventListener('click', listener);
    return () => document.removeEventListener('click', listener);
  }, [locale, page]);
  return null;
}
