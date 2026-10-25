import {MarketingPage} from '@/features/marketing/pages';
import {marketingMetadata} from '@/features/marketing/seo';
export const dynamic = 'force-dynamic';
export const metadata = marketingMetadata('en', 'demo');
export default function Page() {return <MarketingPage locale="en" page="demo" />;}
