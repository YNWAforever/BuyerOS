'use client';

import type { Evidence, Store } from '@/services/contracts';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Button, Field, Pick, Pill } from '../ui';
import { block, money } from '@/services/mock-client';

type Translate = (text: string) => string;

export function DemoSourceDialog({
  source, onClose, t,
}: { source: Evidence | null; onClose: () => void; t: Translate }) {
  return (
    <Dialog open={!!source} onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="source-dialog">
        <DialogTitle>{source?.title}</DialogTitle>
        <DialogDescription>{t('In-app fictional source panel · not a live webpage')}</DialogDescription>
        {source && <>
          <Pill>{source.kind}</Pill>
          <blockquote>{source.excerpt}</blockquote>
          <dl>
            <dt>{t('Sample reference')}</dt><dd>{source.id}</dd>
            <dt>{t('Source type')}</dt><dd>{source.type}</dd>
            <dt>{t('Original source language')}</dt><dd>{source.language}</dd>
            <dt>{t('Displayed excerpt')}</dt><dd>{t('English sample translation / authored fixture')}</dd>
            <dt>{t('Observed (sample)')}</dt><dd>{source.observedAt}</dd>
            <dt>{t('Requirement')}</dt><dd>{source.requirement}</dd>
          </dl>
          <p className="notice">
            {source.contradicts ? 'Contrary or qualifying evidence. ' : 'Direct sample observation. '}
            {t('No source was fetched from the web.')}
          </p>
        </>}
      </DialogContent>
    </Dialog>
  );
}

export function DemoConnectionDialog({
  connection, onClose, t,
}: { connection: string; onClose: () => void; t: Translate }) {
  return (
    <Dialog open={!!connection} onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent>
        <DialogTitle>{connection} · {t('Not connected')}</DialogTitle>
        <DialogDescription>{t('Future backend integration requirements')}</DialogDescription>
        <p>{t('A server-side adapter, workspace authorisation, provider agreement, usage limits, audit events and reviewed data policies are required.')}</p>
        <p>{t('No credentials are collected here. The live adapter fails explicitly until implemented.')}</p>
      </DialogContent>
    </Dialog>
  );
}


type DemoActionDialogProps = {
  t: Translate;
  modal: string;
  store: Store;
  actionIds: string[];
  quote: Store['quotes'][number] | undefined;
  quoteExpired: boolean;
  remainingBudget: number;
  draft: Store['drafts'][number] | undefined;
  selectedListId: string;
  listName: string;
  reason: string;
  onClose: () => void;
  onSaveDraft: () => void;
  onUseSample: () => void;
  onNewSearch: () => void;
  onConfirmQuote: () => void;
  onSelectList: (id: string) => void;
  onSaveToList: () => void;
  onListNameChange: (name: string) => void;
  onSaveList: () => void;
  onReasonChange: (reason: string) => void;
  onConfirmReason: () => void;
};

export function DemoActionDialog({
  t, modal, store, actionIds, quote, quoteExpired, remainingBudget,
  draft, selectedListId, listName, reason, onClose,
  onSaveDraft, onUseSample, onNewSearch, onConfirmQuote, onSelectList,
  onSaveToList, onListNameChange, onSaveList, onReasonChange, onConfirmReason,
}: DemoActionDialogProps) {
  const selectedCompanies = store.companies.filter(company => actionIds.includes(company.id));
  const eligible = selectedCompanies.filter(company => !block(company));
  const selectedList = store.lists.find(list => list.id === selectedListId);
  const title = modal === 'lookup' ? 'Find business contacts'
    : modal === 'reject' ? 'Reject buyer'
    : modal === 'save' ? 'Save to list'
    : modal === 'create-list' ? 'Create list'
    : modal === 'rename-list' ? 'Rename list'
    : modal === 'project' ? 'Active project'
    : modal === 'save-draft' ? 'Save draft on this device'
    : 'Confirm suppression change';
  const description = modal === 'lookup'
    ? 'Illustrative demo quote \u2014 no charge. Work email only. Phone lookup is off.'
    : modal === 'project' ? 'One fictional project is available in this preview.'
    : 'Changes apply only to this demonstration.';

  return <Dialog open={!!modal} onOpenChange={open => { if (!open) onClose(); }}>
    <DialogContent>
      <DialogTitle>{t(title)}</DialogTitle>
      <DialogDescription>{t(description)}</DialogDescription>
      {modal === 'save-draft' ? <>
        <p>{t('This saves the selected synthetic draft on this device, including recipient, subject and body. Only .example recipients are allowed. Approval must be reviewed again after reload. Use Reset demo data to delete it.')}</p>
        <Button disabled={!draft?.recipient.endsWith('.example')} onClick={onSaveDraft}>{t('Save locally')}</Button>
      </> : modal === 'project' ? <>
        <h3>HarbourSense Instruments</h3>
        <p>{t('Industrial sensors \u00b7 Germany, Netherlands, Belgium')}</p>
        <Button onClick={onUseSample}>{t('Use sample project')}</Button>
        <Button variant="outline" onClick={onNewSearch}>{t('New buyer search')}</Button>
      </> : modal === 'lookup' ? <>
        <div className="quote-summary">
          <span>{actionIds.length} {t('selected')}</span>
          <b>{eligible.length} {t('eligible')}</b>
          <span>{actionIds.length - eligible.length} {t('blocked')}</span>
        </div>
        {selectedCompanies.map(company => <div className="quote-row" key={company.id}>
          <b>{company.name}</b><small>{t(block(company) || 'Eligible \u00b7 procurement / operations')}</small>
        </div>)}
        <div className="usage-row"><span>{t('Maximum cost')}</span><b>{money(eligible.length * (store.contactUnitPrice ?? .3))}</b></div>
        <div className="usage-row"><span>{t('Unreserved contact budget')}</span><b>{money(remainingBudget)}</b></div>
        {quote ? <p className="muted">{t('Quote')}{quote.id.slice(0, 8)} {t('\u00b7 expires')}{new Date(quote.expiresAt).toLocaleTimeString()} \u00b7 {money(quote.cost)} {t('reserved')}</p>
          : <p className="error">{t(eligible.length ? 'Contact budget is insufficient. Review the limit in Settings.' : 'No eligible buyers. Review the blocked reasons above.')}</p>}
        <Button disabled={!quote || quoteExpired} onClick={onConfirmQuote}>{t('Confirm sample lookup')}</Button>
        <Button variant="outline" onClick={onClose}>{t('Cancel')}</Button>
      </> : modal === 'save' ? <>
        <Field label="Buyer list"><Pick value={selectedList?.name || store.lists[0]?.name}
          onChange={name => onSelectList(store.lists.find(list => list.name === name)!.id)}
          items={store.lists.map(list => list.name)} /></Field>
        <p>{selectedList?.name}</p>
        <Button onClick={onSaveToList}>{t('Save')}</Button>
      </> : modal === 'create-list' || modal === 'rename-list' ? <>
        <Field label={t('List name')}><input value={listName} onChange={event => onListNameChange(event.target.value)} /></Field>
        <Button disabled={!listName.trim()} onClick={onSaveList}>{t('Save')}</Button>
      </> : <>
        <p>{selectedCompanies.map(company => company.name).join(', ')}</p>
        <Field label="Reason (required)"><textarea value={reason} onChange={event => onReasonChange(event.target.value)} /></Field>
        <Button disabled={!reason.trim()} onClick={onConfirmReason}>{t('Confirm')}</Button>
      </>}
    </DialogContent>
  </Dialog>;
}
