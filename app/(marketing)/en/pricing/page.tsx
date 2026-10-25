import {MarketingPage} from '@/features/marketing/pages';
import {marketingMetadata} from '@/features/marketing/seo';
export const metadata = marketingMetadata('en', 'pricing');
export default function Page() {return <MarketingPage locale="en" page="pricing" />;}
