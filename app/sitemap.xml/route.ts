import {sitemapEntries} from '@/features/marketing/seo';
function xml(value: string) {return value.replace(/[<>&"']/g, char => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[char]!));}
export function GET() {
  const entries = sitemapEntries();
  const urls = entries.map(item => `<url><loc>${xml(item.url)}</loc>${Object.entries(item.alternates.languages).map(([locale, url]) => `<xhtml:link rel="alternate" hreflang="${locale}" href="${xml(url)}"/>`).join('')}</url>`).join('');
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">${urls}</urlset>`, {headers: {'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=300'}});
}
