import type {Metadata} from 'next';
import {siteCopy, pageFaq, type Locale, type PageId} from './content';
import {publicPages, locales, publicPath} from './routes';
import {publishing, type Publisher} from './publishing';

export function marketingMetadata(locale: Locale, page: PageId, publisher: Publisher = publishing()): Metadata {
  const copy = siteCopy[locale].seo[page], path = publicPath(locale, page), origin = publisher.origin;
  return {
    title: copy.title, description: copy.description,
    robots: {index: publisher.indexable, follow: publisher.indexable},
    icons: {icon: '/favicon.svg'},
    ...(origin ? {metadataBase: new URL(origin), alternates: {
      canonical: origin + path,
      languages: {'zh-HK': origin + publicPath('zh-HK', page), en: origin + publicPath('en', page), 'x-default': origin + publicPath('zh-HK', page)},
    }} : {}),
    openGraph: {title: copy.title, description: copy.description, type: 'website', siteName: 'BuyerOS',
      locale: locale === 'zh-HK' ? 'zh_HK' : 'en_US', alternateLocale: locale === 'zh-HK' ? 'en_US' : 'zh_HK',
      ...(origin ? {url: origin + path, images: [{url: `${origin}/marketing/og-${locale}.png`, width: 1200, height: 630, alt: copy.title}]} : {})},
    twitter: {card: 'summary_large_image', title: copy.title, description: copy.description,
      ...(origin ? {images: [`${origin}/marketing/og-${locale}.png`]} : {})},
  };
}

export function structuredData(locale: Locale, page: PageId, publisher: Publisher = publishing()): object[] {
  const copy = siteCopy[locale], origin = publisher.origin;
  const result: object[] = [];
  if (origin && publisher.legalEntity) result.push({'@context': 'https://schema.org', '@type': 'Organization',
    '@id': origin + '/#organization', name: publisher.legalEntity, url: origin,
    ...(publisher.contactEmail ? {email: publisher.contactEmail} : {})});
  if (page === 'home' || page === 'features') result.push({'@context': 'https://schema.org', '@type': 'SoftwareApplication',
    name: 'BuyerOS', applicationCategory: 'BusinessApplication', operatingSystem: 'Web',
    description: copy.seo[page].description, inLanguage: locale,
    ...(origin ? {url: origin + publicPath(locale, page)} : {})});
  if (page === 'home' || page === 'faq') result.push({'@context': 'https://schema.org', '@type': 'FAQPage', inLanguage: locale,
    mainEntity: pageFaq(locale, page).map(item => ({'@type': 'Question', name: item.question, acceptedAnswer: {'@type': 'Answer', text: item.answer}}))});
  return result;
}
export function jsonLd(value: object): string {return JSON.stringify(value).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');}
export function sitemapEntries(publisher: Publisher = publishing()) {
  if (!publisher.indexable || !publisher.origin) return [];
  return locales.flatMap(locale => publicPages.map(page => ({url: publisher.origin! + publicPath(locale, page),
    alternates: {languages: {'zh-HK': publisher.origin! + publicPath('zh-HK', page), en: publisher.origin! + publicPath('en', page)}}})));
}
