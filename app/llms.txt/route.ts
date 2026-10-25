import {siteCopy} from '@/features/marketing/content';
import {locales, publicPages, publicPath} from '@/features/marketing/routes';
import {publishing} from '@/features/marketing/publishing';
export function GET() {
  const origin = publishing().origin ?? '';
  const text = '# BuyerOS\n\nA workspace for buyer criteria, company and source records, human review and saved outreach drafts.\n\n## Scope\n\nResearch depends on configured providers and permissions. Source records are not guarantees of third-party accuracy. Drafts are saved for review; this workflow does not offer sending. All examples on this site are synthetic, not customer outcomes. Prices and free access are not confirmed.\n\n## Public documentation\n\n' + locales.flatMap(locale => publicPages.map(page => `- [${siteCopy[locale].nav[page]} (${locale})](${origin}${publicPath(locale, page)}): ${siteCopy[locale].seo[page].description}`)).join('\n') + '\n';
  return new Response(text, {headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=300'}});
}
