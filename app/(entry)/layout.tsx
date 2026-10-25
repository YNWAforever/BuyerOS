import type {Metadata} from 'next';
import type {ReactNode} from 'react';

export const metadata: Metadata = {robots: {index: false, follow: false}};

export default function EntryLayout({children}: {children: ReactNode}) {
  return <html lang="zh-HK"><body>{children}</body></html>;
}
