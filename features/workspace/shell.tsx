'use client';

import { ChevronRight } from 'lucide-react';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { type DataMode } from '@/services/live/mode';
import { modeBanner } from '@/services/live/workspace-logic';
import { Pick } from '../ui';

type DemoShellHeaderProps = {
  t: (text: string) => string;
  navTitle: string;
  mode: DataMode;
  locale: 'en' | 'zh-HK';
  onLocaleChange: (locale: 'en' | 'zh-HK') => void;
};

export function DemoShellHeader({
  t, navTitle, mode, locale, onLocaleChange,
}: DemoShellHeaderProps) {
  return (
    <header className="topbar">
      <div className="inline">
        <SidebarTrigger />
        <span className="breadcrumb">{t('Workspace')}</span>
        <ChevronRight size={14} />
        <b>{t(navTitle)}</b>
      </div>
      <div className="inline top-right">
        <span className="demo-indicator"><span />{t(modeBanner(mode))}</span>
        <Pick
          value={locale === 'en' ? 'English' : '繁體中文'}
          onChange={value => onLocaleChange(value === 'English' ? 'en' : 'zh-HK')}
          items={['English', '繁體中文']}
          label="Language"
        />
        <div className="avatar small">WL</div>
      </div>
    </header>
  );
}
