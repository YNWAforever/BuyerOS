'use client';

import { ArrowRight, ArrowUpRight, Building2, Check, CheckCheck, ChevronDown, FileText, FolderOpen, Globe2, Info, Mail, Plus, ShieldCheck } from 'lucide-react';
import { Button, Field, Pick, Pill } from '../ui';
import { BuyerDetail } from '../buyers/detail';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import type { ReactNode } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { download, money } from '@/services/mock-client';
import type { Company, Evidence, OutreachDraft, Store } from '@/services/contracts';

type DemoRouteHeadingProps = {
  t: (text: string) => string;
  navTitle: string;
  isWizard: boolean;
  isOverview: boolean;
  isLists: boolean;
  isOutreach: boolean;
  isResults: boolean;
  isSettings: boolean;
  isFull: boolean;
  onProject: () => void;
  onUseSample: () => void;
  onNewSearch: () => void;
};

export function DemoRouteHeading({
  t, navTitle, isWizard, isOverview, isLists, isOutreach,
  isResults, isSettings, isFull, onProject, onUseSample, onNewSearch,
}: DemoRouteHeadingProps) {
  const description = isWizard
    ? 'Define your offer, buyers and a controlled search plan.'
    : isOverview
      ? 'Your next actions, across one connected buyer workspace.'
      : isLists
        ? 'Keep the right companies together and move each buyer forward.'
        : isOutreach
          ? 'Prepare relevant outreach. Keep every decision under human review.'
          : isResults
            ? 'Track explicitly recorded demo outcomes and illustrative usage.'
            : isSettings
              ? 'Manage demo preferences and review connection requirements.'
              : isFull
                ? 'Review the commercial fit and the evidence behind it.'
                : 'Find the right companies. Know why they belong on your list.';

  return <>
    <div className="project-line">
      <button className="project-select" onClick={onProject}>
        <Building2 size={15} /> HarbourSense Instruments <ChevronDown size={14} />
      </button>
      <span className="project-divider" />
      <span>{t('European sensor partners')}</span>
      <Pill>{t('DEMO PROJECT')}</Pill>
    </div>
    <div className="page-heading">
      <div>
        <h1>{t(navTitle)}</h1>
        <p>{t(description)}</p>
      </div>
      {!isWizard && !isSettings && !isOutreach && <div className="inline">
        <Button variant="outline" onClick={onUseSample}>{t('Use sample project')}</Button>
        <Button onClick={onNewSearch}><Plus size={16} />{t('New buyer search')}</Button>
      </div>}
    </div>
  </>;
}


type DemoOutreachViewProps = {
  t: (text: string) => string;
  store: Store;
  draft?: OutreachDraft;
  company?: Company;
  onSelectDraft: (id: string) => void;
  onChooseBuyer: () => void;
  onEditDraft: (patch: Partial<OutreachDraft>) => void;
  onSaveDraft: () => void;
  onRequestReview: () => void;
  onOpenEvidence: (evidence: Evidence) => void;
  onApproveDraft: () => void;
};

export function DemoOutreachView({
  t, store, draft, company, onSelectDraft, onChooseBuyer, onEditDraft,
  onSaveDraft, onRequestReview, onOpenEvidence, onApproveDraft,
}: DemoOutreachViewProps) {
  return <div className="outreach-layout"><section className="panel recipient-queue"><h3>{t("Recipient queue")}<Pill>{store.drafts.length}</Pill></h3>{store.drafts.map(d=><button className={d.id===draft?.id?'active':''} key={d.id} onClick={()=>onSelectDraft(d.id)}><b>{store.companies.find(c=>c.id===d.buyerId)?.name}</b><Pill kind={d.status==='Approved'?'green':'plain'}>{t(d.status)}</Pill><small>{t("Revision")}{d.revision} {t("· Not sent")}</small></button>)}<Button variant="outline" onClick={onChooseBuyer}><Plus size={15}/>{t("Choose accepted buyer")}</Button></section>{draft&&company?<><section className="panel draft-editor"><div className="inline spread"><h2>{t("Email draft")}</h2><Pill>{t(draft.status)}</Pill></div><div className="notice">{t("Template-generated sample · No message has been sent.")}</div><div className="two-col"><Field label="Objective"><input value={draft.objective} onChange={e=>onEditDraft({objective:e.target.value})}/></Field><Field label="Tone"><Pick value={draft.tone} onChange={v=>onEditDraft({tone:v})} items={['Professional','Warm','Concise']}/></Field></div><Field label="Recipient language"><Pick value={draft.language} onChange={v=>onEditDraft({language:v})} items={['English','繁體中文']}/></Field><Field label="Approved value proposition"><input value={draft.valueProposition} onChange={e=>onEditDraft({valueProposition:e.target.value})}/></Field><Button variant="outline" onClick={()=>onEditDraft({subject:draft.language==='English'?draft.objective+' — HarbourSense':'合作建議 — HarbourSense',body:draft.language==='English'?`${draft.tone==='Warm'?'Hello and thank you for your time,':'Hello procurement team,'}\n\n${draft.tone==='Concise'?'Your sample profile describes industrial automation.':'Your sample company profile describes industrial automation capabilities.'}\n\n${draft.valueProposition}\n\nOur objective: ${draft.objective}. Would your team be the right contact to discuss potential requirements?\n\nIf this is not relevant, please let us know and we will not follow up.\n\nBest regards,\n${draft.sender||'HarbourSense team'}`:`採購團隊你好：\n\n示範公司資料提及貴公司的工業自動化業務。\n\n已確認的價值主張：${draft.valueProposition}\n\n聯絡目的：${draft.objective}。請問貴團隊是否負責評估相關需求？\n\n如內容不適用，請告知，我們將不再跟進。\n\n${draft.sender||'HarbourSense 團隊'}`})}>{t('Generate sample draft')}</Button><Field label="Recipient · sample only"><input value={draft.recipient} onChange={e=>onEditDraft({recipient:e.target.value})}/></Field><Field label={t('Subject')}><input value={draft.subject} onChange={e=>onEditDraft({subject:e.target.value})}/></Field><Field label={t('Message')}><textarea className="message-body" value={draft.body} onChange={e=>onEditDraft({body:e.target.value})}/></Field><details><summary>{t("Optional follow-up draft")}</summary><textarea value={draft.followup} onChange={e=>onEditDraft({followup:e.target.value})} placeholder="Write a single optional follow-up…"/></details><div className="draft-actions"><Button variant="outline" onClick={onSaveDraft}>{t('Save')}</Button><Button disabled={!draft.subject.trim()||!draft.body.trim()} onClick={onRequestReview}>{t('Request review')}</Button><Button variant="outline" onClick={async()=>{try{await navigator.clipboard.writeText(draft.subject+'\n\n'+draft.body);toast.success('Draft copied — not sent.')}catch{toast.error('Clipboard unavailable. Use Download sample draft.')}}}>{t('Copy draft')}</Button><Button variant="outline" onClick={()=>download('DEMO_outreach.txt','DEMO — UNSENT\n'+draft.subject+'\n\n'+draft.body)}>{t('Download sample draft')}</Button></div><hr/><Button disabled>{t("Send email")}</Button><p className="muted">{t("Delivery is not connected in this prototype.")}</p></section><aside className="panel review-panel"><h3>{t("Evidence & review")}</h3><p>{company.name}</p><button className="evidence-card" onClick={()=>onOpenEvidence(company.evidence[0])}><FileText size={18}/><b>{t("Fact used in draft")}</b><p>{t("Industrial automation / sensor portfolio.")}</p><span className="text-blue">{t("View sample evidence")}<ArrowUpRight size={14}/></span></button><h3>{t("Review requirements")}</h3>{[[company.review==='Accepted','Buyer accepted'],[company.contact==='Provider-marked valid','Sample contact marked valid'],[!company.suppressed,'Not suppressed'],[!!draft.sender.trim(),'Sender identity entered'],[/not follow up|不再跟進/i.test(draft.body),'Opt-out wording included']].map(([ok,l])=><div className="review-check" key={l as string}><span className={ok?'ok':'not-ok'}>{ok?<Check size={13}/>:<Info size={13}/>}</span>{l as string}</div>)}<Field label="Sender identity · demo"><input value={draft.sender} onChange={e=>onEditDraft({sender:e.target.value})} placeholder="HarbourSense team"/></Field><label className="check-line"><Checkbox checked={draft.policyReviewed} onCheckedChange={v=>onEditDraft({policyReviewed:!!v})}/>{t("Jurisdiction / policy reviewed (demo)")}</label><p className="muted">{t("Policy review required. This checklist is not a legal compliance determination.")}</p><Button disabled={draft.status!=='In review'||company.review!=='Accepted'||company.contact!=='Provider-marked valid'||company.suppressed||!draft.policyReviewed||!draft.sender.trim()||!(/not follow up|不再跟進/i.test(draft.body))||draft.recipient!==('purchasing@'+company.name.split(' ')[0].toLowerCase()+'.example')} onClick={onApproveDraft}>{t('Approve draft')}</Button>{draft.status==='Approved'&&<p className="notice">{t("Approved revision")}{draft.approvedRevision} {t("by")}{draft.approver} {t("at")}{draft.approvedAt}{t(". Editing invalidates approval.")}</p>}</aside></>:<section className="panel empty"><Mail size={32}/><h2>{t("Start with an accepted buyer")}</h2><p>{t("Review a buyer, then choose Prepare draft.")}</p><Button onClick={onChooseBuyer}>{t("Choose buyer")}</Button></section>}</div>;
}

type DemoDiscoveryRunViewProps = {
  t: (text: string) => string;
  store: Store;
  run: Store['runs'][number];
  onFitFilter: (fit: 'Match' | 'Needs review') => void;
  onReviewMatches: () => void;
  onCancel: () => void;
  onRetry: () => void;
  onEditBudget: () => void;
  onSelectRun: (id: string) => void;
  children: ReactNode;
};

const demoStages = ['Prepare profile', 'Generate queries', 'Discover companies', 'Remove duplicates', 'Assess evidence', 'Results ready'];

export function DemoDiscoveryRunView({
  t, store, run, onFitFilter, onReviewMatches, onCancel, onRetry,
  onEditBudget, onSelectRun, children,
}: DemoDiscoveryRunViewProps) {
  const candidates = store.companies.slice(0, run.count);
  const discoveryCost = store.costs
    .filter(cost => run.id === 'sample-run' ? cost.eventId.startsWith('sample-') : cost.eventId.startsWith(run.id + ':'))
    .reduce((total, cost) => total + cost.amount, 0);
  return <>
    <section className="run-summary">
      <div className="inline spread">
        <div className="inline"><span className="run-icon"><Globe2 size={21} /></span>
          <div><h2>{t('Industrial sensor buyers in Europe')}</h2>
            <p>{t('Germany, Netherlands, Belgium')}<span>·</span> {t('Distributors & system integrators')}</p>
          </div>
        </div>
        <div className="run-status">
          <Pill kind={run.status === 'Completed' ? 'green' : 'amber'}><Check size={13} />{t(run.status)}</Pill>
          <small>{t('Sample run · Profile v')}{run.profileVersion}</small>
        </div>
      </div>
      <div className="run-metrics">
        <div><strong>{run.count}</strong><span>{t('Unique companies')}</span></div>
        <button onClick={() => onFitFilter('Match')}><strong>{candidates.filter(company => company.fit === 'Match').length}<span className="tiny green">{t('Match')}</span></strong><span>{t('Fit your requirements')}</span></button>
        <button onClick={() => onFitFilter('Needs review')}><strong>{candidates.filter(company => company.fit === 'Needs review').length}<span className="tiny amber">{t('Review')}</span></strong><span>{t('Need a closer look')}</span></button>
        <div><strong>{money(discoveryCost)}</strong><span>{t('Illustrative discovery spend')}</span></div>
        <div className="dedup"><CheckCheck size={16} /><span>{run.rawCount} {t('raw candidates')}<br />{Math.max(0, run.rawCount - run.count)} {t('duplicates merged')}</span></div>
      </div>
    </section>
    {run.status !== 'Completed' && <div className="panel job-panel" aria-live="polite">
      <div className="inline spread">
        <h3>{run.status === 'Running' ? 'Demo sequence · ' + demoStages[Math.min(run.stage, 5)] : t(run.status)}</h3>
        <span>{run.stage} {t('/ 6 stages ·')}{run.stage * .7}{t('s demo time')}</span>
      </div>
      <Progress value={run.stage / 6 * 100} />
      <p>{t('Deterministic simulation. No web research or paid service was called.')}{run.status === 'Limited demonstration' ? t('This offer or profile is outside the supplied fixture dataset. Use the sample project to explore results.') : ''}</p>
      <div className="inline">
        {run.status === 'Running' && <Button variant="outline" onClick={onCancel}>{t('Cancel')}</Button>}
        {['Failed', 'Cancelled', 'Provider unavailable'].includes(run.status) && <Button onClick={onRetry}>{t('Retry demo')}</Button>}
        {run.status === 'Paused at budget cap' && <Button onClick={onEditBudget}>{t('Edit budget in a new search')}</Button>}
      </div>
    </div>}
    <div className="next-action">
      <div className="next-action-icon"><ShieldCheck size={19} /></div>
      <div><b>{t('Review your best-fit buyers')}</b><p>{t('Review evidence before accepting a company. Contact lookup stays optional.')}</p></div>
      <Button variant="ghost" onClick={onReviewMatches}>{t('Review matches')}<ArrowRight size={16} /></Button>
    </div>
    {children}
    <details className="run-history">
      <summary>{t('Search run history')}</summary>
      {store.runs.map(historyRun => <button key={historyRun.id} onClick={() => onSelectRun(historyRun.id)}>
        <b>{historyRun.id === 'sample-run' ? 'Sample run' : historyRun.id.slice(0, 12)}</b>
        <span>{t(historyRun.status)} · {historyRun.count} companies · Profile v{historyRun.profileVersion}</span>
      </button>)}
    </details>
  </>;
}

type DemoListsViewProps = {
  t: (text: string) => string;
  lists: Store['lists'];
  currentListId?: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: () => void;
};

export function DemoListsView({
  t, lists, currentListId, onSelect, onCreate, onRename,
}: DemoListsViewProps) {
  return <>
    <div className="list-strip">
      {lists.map(list => <button key={list.id} className={list.id === currentListId ? 'active' : ''}
        onClick={() => onSelect(list.id)}>
        <FolderOpen size={18} />
        <span>{list.name}<small>{list.members.length} {t('companies')}</small></span>
      </button>)}
      <Button variant="outline" onClick={onCreate}><Plus size={16} />{t('Create list')}</Button>
    </div>
    <div className="inline list-actions">
      <Button variant="ghost" onClick={onRename}>{t('Rename list')}</Button>
    </div>
  </>;
}

type DemoOverviewViewProps = {
  t: (text: string) => string;
  store: Store;
  pending: number;
  accepted: number;
  runStatus: string;
  onAwaitingReview: () => void;
  onAcceptedWithoutContact: () => void;
  onDraftsInReview: () => void;
  onCreateProject: () => void;
  onContinue: () => void;
};

export function DemoOverviewView({
  t, store, pending, accepted, runStatus,
  onAwaitingReview, onAcceptedWithoutContact, onDraftsInReview,
  onCreateProject, onContinue,
}: DemoOverviewViewProps) {
  const metrics = [
    { count: pending, label: 'Buyers awaiting review', onClick: onAwaitingReview },
    {
      count: store.companies.filter(company => company.review === 'Accepted' && company.contact === 'Not researched').length,
      label: 'Accepted buyers needing contacts',
      onClick: onAcceptedWithoutContact,
    },
    { count: store.drafts.filter(draft => draft.status === 'In review').length, label: 'Drafts awaiting approval', onClick: onDraftsInReview },
  ];
  return <>
    <div className="overview-cards">{metrics.map(metric =>
      <button className="panel metric-card" key={metric.label} onClick={metric.onClick}>
        <span>{t(metric.label)}</span><strong>{metric.count}</strong><ArrowUpRight size={20} />
      </button>)}</div>
    <div className="section-heading"><h2>{t('Projects')}</h2>
      <Button variant="outline" onClick={onCreateProject}><Plus size={16} />{t('Create project')}</Button>
    </div>
    <div className="panel project-card">
      <div className="run-icon"><Building2 /></div>
      <h2>HarbourSense Instruments</h2>
      <p>{t('Industrial sensing for process monitoring and automation.')}</p>
      <div className="inline">{['Germany', 'Netherlands', 'Belgium'].map(market => <Pill key={market}>{t(market)}</Pill>)}</div>
      <hr />
      <div className="inline spread">
        <span>{accepted} {t('accepted buyers ·')}{runStatus}</span>
        <Button onClick={onContinue}>{t('Continue last search')}<ArrowRight size={16} /></Button>
      </div>
    </div>
    <h2 className="section-heading">{t('Demo activity')}</h2>
    <div className="panel">
      {store.companies.filter(company => company.activity.length > 1).slice(0, 5).map(company =>
        <div className="activity" key={company.id}><Check size={16} />
          <div><b>{company.name}</b><p>{company.activity[0]}</p></div>
        </div>)}
      <p className="muted">{t('Sample search completed: 26 raw candidates → 24 unique companies.')}</p>
    </div>
  </>;
}

type DemoResultsViewProps = {
  t: (text: string) => string;
  store: Store;
  usage: { spent: number; reserved: number; remaining: number; accepted: number; valid: number };
  tab: string;
  onTabChange: (tab: string) => void;
  onOpenBuyer: (id: string) => void;
  onRecordOutcome: (buyerId: string, stage: string) => void;
};

export function DemoResultsView({
  t, store, usage, tab, onTabChange, onOpenBuyer, onRecordOutcome,
}: DemoResultsViewProps) {
  const stages = ['Reply', 'Meeting', 'Opportunity', 'Disqualified'];
  const categories = ['Discovery', 'Extraction', 'Assessment', 'Contact lookup'];
  const metrics: [number, string][] = [
    [usage.spent, 'Total simulated spend'],
    [usage.reserved, 'Contact budget reserved'],
    [usage.remaining, 'Contact budget remaining'],
  ];

  return <Tabs value={tab} onValueChange={onTabChange}>
    <TabsList>{['Outcomes', 'Usage'].map(value => <TabsTrigger key={value} value={value}>{t(value)}</TabsTrigger>)}</TabsList>
    <TabsContent value="Outcomes">
      <div className="notice">{t('Manually recorded fictional outcomes. No inbox is synchronised. Draft approval never marks an email as sent.')}</div>
      <div className="overview-cards pipeline">{stages.map(stage =>
        <div className="panel metric-card" key={stage}>
          <span>{t(stage)}</span><strong>{store.outcomes.filter(outcome => outcome.stage === stage).length}</strong>
        </div>)}</div>
      <div className="panel">{store.companies.filter(company => company.review === 'Accepted').map(company =>
        <div className="outcome-row" key={company.id}>
          <button onClick={() => onOpenBuyer(company.id)}>{company.name}</button>
          <Pick label={t('Record demo outcome')}
            value={store.outcomes.find(outcome => outcome.buyerId === company.id)?.stage || 'Record demo outcome'}
            onChange={stage => onRecordOutcome(company.id, stage)}
            items={['Record demo outcome', ...stages]} />
        </div>)}</div>
    </TabsContent>
    <TabsContent value="Usage">
      <div className="notice">{t('Illustrative demo spend — no charge. All costs are simulated assumptions.')}</div>
      <div className="overview-cards">{metrics.map(([value, label]) =>
        <div className="panel metric-card" key={label}><span>{t(label)}</span><strong>{money(value)}</strong></div>)}</div>
      <div className="panel">
        <h2>{t('Usage breakdown')}</h2>
        {categories.map(category => <div className="usage-row" key={category}>
          <span>{t(category)}</span>
          <strong>{money(store.costs.filter(cost => cost.category === category).reduce((total, cost) => total + cost.amount, 0))}</strong>
        </div>)}
        <div className="usage-row"><span>{t('Cost per accepted buyer (')}{usage.accepted} {t('distinct companies)')}</span><strong>{usage.accepted ? money(usage.spent / usage.accepted) : '—'}</strong></div>
        <div className="usage-row"><span>{t('Cost per accepted buyer with a valid sample contact (')}{usage.valid} {t('distinct companies)')}</span><strong>{usage.valid ? money(usage.spent / usage.valid) : '—'}</strong></div>
        <p className="muted">{t('Total simulated spend divided by the stated distinct-company count. Quotes are estimates until confirmed; expired and cancelled quotes are excluded from reservations.')}</p>
      </div>
    </TabsContent>
  </Tabs>;
}


type BudgetKey = 'budget' | 'discoveryBudget' | 'contactUnitPrice';
type DemoSettingsViewProps = {
  t: (text: string) => string;
  store: Store;
  savedLocal: boolean;
  selectedCompanyId: string;
  onLocaleChange: (locale: Store['locale']) => void;
  onDefaultMarketsChange: (value: string) => void;
  onBudgetChange: (key: BudgetKey, value: number) => void;
  onSaveLocally: () => void;
  onReset: () => void;
  onSelectCompany: (id: string) => void;
  onSuppression: (id: string, kind: 'suppress' | 'unsuppress') => void;
  onConnection: (connection: string) => void;
};

export function DemoSettingsView({
  t, store, savedLocal, selectedCompanyId, onLocaleChange,
  onDefaultMarketsChange, onBudgetChange, onSaveLocally, onReset,
  onSelectCompany, onSuppression, onConnection,
}: DemoSettingsViewProps) {
  const traditionalChinese = '\u7e41\u9ad4\u4e2d\u6587';
  const budgetFields: [BudgetKey, string][] = [
    ['budget', 'Contact budget (USD)'],
    ['discoveryBudget', 'Discovery budget (USD)'],
    ['contactUnitPrice', 'Sample lookup price per company (USD)'],
  ];
  const selectedCompany = store.companies.find(company => company.id === selectedCompanyId);
  return <div className="settings-grid">
    <section className="panel">
      <h2>{t('Demo preferences')}</h2>
      <Field label="Language"><Pick value={store.locale === 'en' ? 'English' : traditionalChinese}
        onChange={value => onLocaleChange(value === 'English' ? 'en' : 'zh-HK')}
        items={['English', traditionalChinese]} /></Field>
      <Field label="Default markets"><input value={store.defaultMarkets}
        onChange={event => onDefaultMarketsChange(event.target.value)} /></Field>
      {budgetFields.map(([key, label]) => <Field key={key} label={label}>
        <input type="number" min="0" value={store[key]}
          onChange={event => onBudgetChange(key, Number(event.target.value))} />
      </Field>)}
      <p className="notice">{t('Edits and entered text stay in memory by default. “Save locally” stores only synthetic workflow states on this device; free-text notes, recipients, drafts, files and custom offers are excluded.')}</p>
      <Button variant="outline" onClick={onSaveLocally}>{t('Save locally')}</Button>
      {savedLocal && <p className="muted">{t('Saved. Draft content remains session-only.')}</p>}
      <Button variant="destructive" onClick={onReset}>{t('Reset demo data')}</Button>
    </section>
    <section className="panel">
      <h2>{t('Suppression list')}</h2>
      <p>{t('Suppression blocks contact lookup and outreach approval.')}</p>
      {store.companies.filter(company => company.suppressed).map(company =>
        <div className="suppression-row" key={company.id}>
          <b>{company.name}</b>
          <Button variant="outline" onClick={() => onSuppression(company.id, 'unsuppress')}>{t('Remove suppression')}</Button>
        </div>)}
      <Field label="Company"><Pick value={selectedCompany?.name || 'Choose company'}
        onChange={value => onSelectCompany(store.companies.find(company => company.name === value)?.id || '')}
        items={['Choose company', ...store.companies.map(company => company.name)]} /></Field>
      <p>{selectedCompany?.name}</p>
      <Button disabled={!selectedCompany} onClick={() => onSuppression(selectedCompanyId, 'suppress')}>{t('Add suppression')}</Button>
      <hr />
      <h2>{t('Connections')}</h2>
      {['Research', 'Contact enrichment', 'Mailbox', 'CRM'].map(connection =>
        <div className="connection" key={connection}>
          <div><b>{t(connection)}</b><small>{t('Not connected')}</small></div>
          <Button variant="ghost" onClick={() => onConnection(connection)}>{t('View requirements')}<ArrowUpRight size={15} /></Button>
        </div>)}
    </section>
  </div>;
}


type DemoFullBuyerViewProps = {
  buyer?: Company;
  t: (value: string) => string;
  action: (name: string, ids: string[]) => void;
  source: (evidence: Evidence) => void;
  update: (id: string, patch: Partial<Company>) => void;
  onReturn: () => void;
};

export function DemoFullBuyerView({
  buyer, t, action, source, update, onReturn,
}: DemoFullBuyerViewProps) {
  if (!buyer) {
    return <div className="empty">
      {t('Buyer not found')}
      <Button onClick={onReturn}>{t('Return to buyers')}</Button>
    </div>;
  }
  return <div className="panel full-dossier">
    <Button variant="ghost" onClick={onReturn}>{t('Return to buyers')}</Button>
    <BuyerDetail c={buyer} t={t} action={action} source={source} update={update} full={onReturn} />
  </div>;
}
