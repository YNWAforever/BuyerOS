import {MarketingPage} from '@/features/marketing/pages';
import {marketingMetadata} from '@/features/marketing/seo';
export const metadata = marketingMetadata('zh-HK', 'terms');
export default function Page() {return <MarketingPage locale="zh-HK" page="terms" />;}
