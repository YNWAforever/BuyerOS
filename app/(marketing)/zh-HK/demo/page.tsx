import {MarketingPage} from '@/features/marketing/pages';
import {marketingMetadata} from '@/features/marketing/seo';
export const dynamic = 'force-dynamic';
export const metadata = marketingMetadata('zh-HK', 'demo');
export default function Page() {return <MarketingPage locale="zh-HK" page="demo" />;}
