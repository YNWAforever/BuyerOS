'use client';
import type {Locale, PageId} from './content';
import {publicPath} from './routes';

export type MarketingEventName = 'cta_click' | 'locale_change' | 'demo_form_start' | 'demo_submit_success';
export function marketingEvent(name: MarketingEventName, locale: Locale, page: PageId, position: string) {
  // Local integration hook only. No cookies, storage, remote provider or form data.
  window.dispatchEvent(new CustomEvent('buyeros:marketing', {detail: {
    name, locale, path: publicPath(locale, page), position: position.slice(0, 40),
  }}));
}
