'use client';
import type {ReactNode} from 'react';

type Props = {
  t: (value:string)=>string;
  email: string | null;
  workspaceName: string | null;
  roles: string[];
  authorized: boolean;
  locale: 'en'|'zh-HK';
  onLocale: (value:'en'|'zh-HK')=>void;
  localeSaving: boolean;
  localeDisabled: boolean;
  accessDetails: ReactNode;
  accessChecking: boolean;
  accessError: string;
  diagnostic: ReactNode;
  onRetryAccess: ()=>void;
  onSignOut: ()=>void;
};

/**
 * The single account control: identity, language, access diagnostics and sign-out live
 * here instead of competing with the daily surface. Workspace administration stays in
 * the navigation's Manage group so the same label never appears twice.
 */
export function AccountMenu({t,email,workspaceName,roles,authorized,locale,onLocale,localeSaving,localeDisabled,accessDetails,accessChecking,accessError,diagnostic,onRetryAccess,onSignOut}:Props){
  const name=workspaceName||email||t('Account');
  return <details className="live-account">
    <summary aria-label={t('Account menu')}>
      <span className="avatar" aria-hidden="true">{name.slice(0,1).toUpperCase()}</span>
      <span className="live-account-id"><b>{name}</b>{email&&<small>{email}</small>}</span>
    </summary>
    <div className="live-account-panel">
      {email&&<p className="live-account-line">{t('Signed in as')}: <b>{email}</b></p>}
      {authorized&&roles.length>0&&<p className="live-account-line">{t('Role')}: {roles.map(t).join(', ')}</p>}
      <label className="live-account-language">{t('Language')}
        <select aria-label={t('Language')} value={locale} onChange={event=>onLocale(event.target.value as 'en'|'zh-HK')} disabled={localeSaving||localeDisabled}>
          <option value="en">English</option><option value="zh-HK">繁體中文</option>
        </select></label>
      {authorized&&<details className="live-access-details"><summary>{t('Access details')}</summary>{accessDetails}</details>}
      {authorized&&<button type="button" className="live-account-action" onClick={onRetryAccess} disabled={accessChecking}>{t(accessChecking?'Checking access…':'Check access again')}</button>}
      {authorized&&accessError&&<p role="alert" className="live-account-alert">{t(accessError)}</p>}
      {diagnostic}
      <button type="button" className="live-account-action" onClick={onSignOut}>{t('Sign out')}</button>
    </div>
  </details>;
}
