import {MarketingPage} from '@/features/marketing/pages';
import {marketingMetadata} from '@/features/marketing/seo';
export const metadata = marketingMetadata('en', 'privacy');
export default function Page() {return <MarketingPage locale="en" page="privacy" />;}
