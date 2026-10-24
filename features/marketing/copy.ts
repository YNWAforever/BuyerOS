import {notFound} from 'next/navigation';

// One server-side source for the bilingual compatibility sample.
export const marketingCopy = {
  'zh-HK': {
    title: 'BuyerOS｜從買家條件到有根據的跟進',
    description: '整理買家條件、公司與來源記錄，經人手審閱後儲存跟進草稿。',
    headline: '買家名單不少，真正值得跟進的是誰？',
    intro: '把買家條件、公司與來源記錄放在同一個工作區，審閱後再準備跟進草稿。',
    preview: '相容性預覽', skip: '跳至主要內容', navigation: '主要導覽',
    login: '登入', cta: '預約示範', workflowLink: '查看工作流程',
    workflow: '由條件到跟進，保留人手判斷',
    steps: [
      {title: '訂立買家條件', body: '集中整理目標市場、公司條件與研究要求。'},
      {title: '審閱公司與來源', body: '查看研究記錄及來源，判斷哪些公司值得繼續了解。'},
      {title: '儲存跟進草稿', body: '整理可供人手審閱的跟進內容，草稿不會自動發送。'},
    ],
    demoTitle: '一起看看 BuyerOS 如何配合你的買家研究流程',
    demoNotice: '此預覽尚未收集示範申請。聯絡方式及申請表會在確認資料處理安排後提供。',
    scope: '此頁用作驗證雙語公開頁與產品工作區的相容性；真實研究服務及正式登入尚未在此驗收。',
    alternateLocale: 'en', alternateLabel: 'English',
  },
  en: {
    title: 'BuyerOS | From buyer criteria to informed follow-up',
    description: 'Organize buyer criteria, company and source records, then save outreach drafts for human review.',
    headline: 'Plenty of buyer names. Who deserves a closer look?',
    intro: 'Bring buyer criteria, company and source records into one workspace. Review them before preparing a follow-up draft.',
    preview: 'Compatibility preview', skip: 'Skip to content', navigation: 'Main navigation',
    login: 'Log in', cta: 'Request a demo', workflowLink: 'See the workflow',
    workflow: 'From criteria to follow-up, with human judgment',
    steps: [
      {title: 'Define buyer criteria', body: 'Organize target markets, company criteria and research requirements.'},
      {title: 'Review companies and sources', body: 'Inspect research records and sources to decide which companies deserve a closer look.'},
      {title: 'Save a follow-up draft', body: 'Prepare content for human review. Drafts are not sent automatically.'},
    ],
    demoTitle: 'Explore how BuyerOS fits your buyer research workflow',
    demoNotice: 'Demo requests are not collected in this preview. Contact details and an intake form will follow once data handling is confirmed.',
    scope: 'This page checks compatibility between bilingual public pages and the product workspace. Real research services and production sign-in have not been accepted here.',
    alternateLocale: 'zh-HK', alternateLabel: '繁體中文',
  },
} as const;

export function publicCopy(locale: string) {
  if (locale !== 'zh-HK' && locale !== 'en') notFound();
  return marketingCopy[locale];
}
