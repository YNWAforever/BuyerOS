import type {Locale, PageId} from './content';

export const locales: readonly Locale[] = ['zh-HK', 'en'];
export const publicPages: readonly PageId[] = ['home', 'features', 'how-it-works', 'pricing', 'faq', 'demo', 'privacy', 'terms'];
export function publicPath(locale: Locale, page: PageId = 'home'): string {
  return `/${locale}${page === 'home' ? '' : `/${page}`}`;
}
export function otherLocale(locale: Locale): Locale {return locale === 'en' ? 'zh-HK' : 'en';}
