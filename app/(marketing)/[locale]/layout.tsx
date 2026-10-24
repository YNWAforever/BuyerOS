import type {Metadata} from 'next';
import type {ReactNode} from 'react';
import {publicCopy} from '@/features/marketing/copy';
import '@/features/marketing/marketing.css';

type Props = {params: Promise<{locale: string}>};

export async function generateMetadata({params}: Props): Promise<Metadata> {
  const copy = publicCopy((await params).locale);
  return {
    title: copy.title, description: copy.description,
    // This spike is a preview, not a published marketing site.
    robots: {index: false, follow: false}, icons: {icon: '/favicon.svg'},
  };
}

export default async function MarketingLayout({children, params}: Props & {children: ReactNode}) {
  const {locale} = await params;
  publicCopy(locale);
  return <html lang={locale}><body className="marketing-shell">{children}</body></html>;
}
