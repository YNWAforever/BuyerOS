import type {ReactNode} from 'react';
import {PublicDocument} from '@/features/marketing/site';
export default function Layout({children}: {children: ReactNode}) {
  return <PublicDocument locale="zh-HK">{children}</PublicDocument>;
}
