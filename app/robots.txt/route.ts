import {publishing} from '@/features/marketing/publishing';
export function GET() {
  const site = publishing();
  const text = site.indexable
    ? `User-agent: *\nAllow: /zh-HK\nAllow: /en\nDisallow: /app\nDisallow: /auth\nDisallow: /api\nDisallow: /v1\nSitemap: ${site.origin}/sitemap.xml\n`
    : 'User-agent: *\nDisallow: /\n';
  return new Response(text, {headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=300'}});
}
