'use client';
import './demo-form.css';
import {useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent} from 'react';
import type {Locale, SiteCopy} from './content';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {Button} from '@/components/ui/button';
import {marketingEvent} from './events';

type Fields = {name: string; email: string; company: string; message: string};
type Receipt = {receipt_id: string; synthetic: boolean};
const receiptKey = 'buyeros.marketing.receipt.v1', intentKey = 'buyeros.marketing.intent.v1';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const subscribe = () => () => {};
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Invalid response');
  return value as Record<string, unknown>;
}
function validEmail(value: string, synthetic: boolean): boolean {
  const at = value.lastIndexOf('@'), local = value.slice(0, at), domain = value.slice(at + 1);
  return at > 0 && value.length <= 254 && local.length <= 64 && domain.length <= 253 && domain.includes('.') &&
    /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$/.test(local) && !local.startsWith('.') && !local.endsWith('.') && !local.includes('..') &&
    domain.split('.').every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) &&
    (!synthetic || domain.endsWith('.test'));
}
function savedReceipt(): Receipt | null {
  try {const value = JSON.parse(sessionStorage.getItem(receiptKey) ?? 'null');return value && uuid.test(value.receipt_id) && typeof value.synthetic === 'boolean' ? value : null;} catch {return null;}
}
export function DemoForm({locale, copy, enabled, synthetic}: {locale: Locale; copy: SiteCopy['form']; enabled: boolean; synthetic: boolean}) {
  const browser = useSyncExternalStore(subscribe, () => true, () => false);
  const [fields, setFields] = useState<Fields>({name: '', email: '', company: '', message: ''});
  const [receipt, setReceipt] = useState<Receipt | null>(savedReceipt);
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  const [errors, setErrors] = useState<Partial<Record<keyof Fields | 'consent', string>>>({});
  const [consent, setConsent] = useState(false);
  const challenge = useRef<{id: string; at: number} | null>(null), challengeRequest = useRef<Promise<{id: string; at: number}> | null>(null);
  const started = useRef(false), busy = useRef(false), mounted = useRef(false), form = useRef<HTMLFormElement>(null);
  const intent = useRef<{fingerprint: string; key: string} | null>(null);
  const getChallenge = useCallback(async () => {
    if (challenge.current && Date.now() - challenge.current.at < 14 * 60_000) return challenge.current;
    if (!challengeRequest.current) challengeRequest.current = (async () => {
      const response = await fetch('/api/marketing/leads/challenge', {cache: 'no-store', credentials: 'omit'});
      const value = object(await response.json());
      if (!response.ok || typeof value.challenge_id !== 'string' || !uuid.test(value.challenge_id)) throw Error('Challenge unavailable');
      const issued = {id: value.challenge_id as string, at: Date.now()};challenge.current = issued;return issued;
    })().finally(() => {challengeRequest.current = null;});
    return challengeRequest.current;
  }, []);
  useEffect(() => {
    mounted.current = true;
    if (enabled) void getChallenge().catch(() => {if (mounted.current) setError(copy.error);});
    return () => {mounted.current = false;};
  }, [enabled, getChallenge, copy.error]);
  function change(name: keyof Fields, value: string) {
    setFields(current => ({...current, [name]: value}));
    setErrors(current => ({...current, [name]: undefined}));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();if (!enabled || !browser || busy.current) return;
    const website = new FormData(event.currentTarget).get('website') ?? '';
    const payload = {name: fields.name.trim(), email: fields.email.trim().toLowerCase(), company: fields.company.trim(), message: fields.message.trim(), locale};
    const nextErrors: typeof errors = {};
    if (!payload.name || payload.name.length > 120) nextErrors.name = copy.invalidName;
    if (!validEmail(payload.email, synthetic)) nextErrors.email = copy.invalidEmail;
    if (payload.company.length > 160) nextErrors.company = copy.invalidCompany;
    if (payload.message.length > 2000) nextErrors.message = copy.invalidMessage;
    if (!consent) nextErrors.consent = copy.privacy;
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      const first = Object.keys(nextErrors)[0];form.current?.querySelector<HTMLInputElement>(`[name="${first}"]`)?.focus();return;
    }
    busy.current = true;setPending(true);setError('');
    try {
      const fingerprint = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(payload))))).map(n => n.toString(16).padStart(2, '0')).join('');
      if (!intent.current) {try {intent.current = JSON.parse(sessionStorage.getItem(intentKey) ?? 'null');} catch { /* In-memory retry still works. */ }}
      if (intent.current?.fingerprint !== fingerprint || !uuid.test(intent.current.key)) intent.current = {fingerprint, key: crypto.randomUUID()};
      try {sessionStorage.setItem(intentKey, JSON.stringify(intent.current));} catch { /* No names, email or message are persisted. */ }
      const issued = await getChallenge();
      await new Promise(resolve => setTimeout(resolve, Math.max(0, 2100 - (Date.now() - issued.at))));
      const response = await fetch('/api/marketing/leads', {method: 'POST', credentials: 'omit', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'Idempotency-Key': intent.current.key},
        body: JSON.stringify({...payload, challenge_id: issued.id, website}),
      });
      const value = object(await response.json());
      if (![200,201].includes(response.status) || value.status !== 'received' || typeof value.receipt_id !== 'string' || !uuid.test(value.receipt_id) || value.synthetic !== synthetic) {
        if (value.code === 'challenge_invalid') challenge.current = null;
        const message = response.status === 409 ? copy.conflict : response.status === 429 ? copy.rateLimited : copy.error;
        if (mounted.current) setError(message);return;
      }
      const saved = {receipt_id: value.receipt_id as string, synthetic: value.synthetic as boolean};
      try {sessionStorage.setItem(receiptKey, JSON.stringify(saved));} catch { /* Receipt remains visible in memory. */ }
      if (mounted.current) {setReceipt(saved);marketingEvent('demo_submit_success', locale, 'demo', 'form');}
    } catch {if (mounted.current) setError(copy.error);}
    finally {busy.current = false;if (mounted.current) setPending(false);}
  }
  if (browser && enabled && receipt?.synthetic === synthetic) return <section className="m-demo-form m-receipt" role="status" aria-live="polite"><h2>{synthetic ? copy.syntheticSuccess : copy.success}</h2><p>{copy.receiptLabel}</p><code>{receipt.receipt_id}</code></section>;
  return <form ref={form} className="m-demo-form" method="post" action="/api/marketing/leads" aria-label={copy.start} noValidate onSubmit={submit} onFocusCapture={() => {
    if (enabled && !started.current) {started.current = true;marketingEvent('demo_form_start', locale, 'demo', 'form');}
  }}>
    {(!enabled || synthetic) && <p className="m-form-notice" role="status">{enabled ? copy.syntheticNotice : copy.unavailable}</p>}
    {enabled && <noscript><p className="m-form-notice">{copy.noJavaScript}</p></noscript>}
    {error && <div className="m-form-errors" role="alert">{error}</div>}
    <fieldset disabled={!enabled || !browser || pending}>
      {(['name','email','company'] as const).map(name => <div className="m-form-field" key={name}>
        <label htmlFor={`demo-${name}`}>{copy[name]}{name === 'company' && <span>{copy.optional}</span>}</label>
        <Input id={`demo-${name}`} name={name} type={name === 'email' ? 'email' : 'text'} autoComplete={name === 'company' ? 'organization' : name}
          maxLength={name === 'email' ? 254 : name === 'company' ? 160 : 120} required={name !== 'company'} value={fields[name]} onChange={event => change(name, event.target.value)}
          aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `demo-${name}-error` : undefined} />
        {errors[name] && <p id={`demo-${name}-error`} role="alert">{errors[name]}</p>}
      </div>)}
      <div className="m-form-field"><label htmlFor="demo-message">{copy.message} <span>{copy.optional}</span></label><Textarea id="demo-message" name="message" maxLength={2000} value={fields.message} onChange={event => change('message', event.target.value)} aria-invalid={Boolean(errors.message)} aria-describedby={errors.message ? 'demo-message-error' : undefined} />{errors.message && <p id="demo-message-error" role="alert">{errors.message}</p>}</div>
      <div className="m-honeypot" aria-hidden="true"><label htmlFor="demo-website">Website</label><input id="demo-website" name="website" tabIndex={-1} autoComplete="off" /></div>
      <label className="m-form-consent"><input type="checkbox" name="consent" checked={consent} onChange={event => setConsent(event.target.checked)} aria-invalid={Boolean(errors.consent)} />{copy.consent}</label>
      {errors.consent && <p role="alert" className="m-form-errors">{errors.consent}</p>}
      <Button className="m-button" type="submit" disabled={!enabled || !browser || pending}>{pending ? copy.pending : copy.submit}</Button>
    </fieldset>
  </form>;
}
