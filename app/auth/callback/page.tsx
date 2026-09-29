'use client';
import {useEffect, useRef, useState} from 'react';
import {useRouter} from 'next/navigation';
import {useWorkspaceSession} from '@/features/providers/workspace-session';

export default function AuthCallbackPage() {
  const {auth, session} = useWorkspaceSession();
  const router = useRouter();
  const [error, setError] = useState('');
  const completion = useRef<Promise<void> | null>(null);
  useEffect(() => {
    let active = true;
    if (!auth) return;
    // React may replay effects in development; one callback code can only be exchanged once.
    completion.current ??= auth.completeCallback();
    void completion.current.then(async () => {
      if (!active) return;
      const token = await auth.getAccessToken();
      if (!active) return;
      session.setToken(token);
      session.next({actor: auth.subject(), workspace: null, project: null});
      router.replace(auth.returnPath());
    }).catch(() => { if (active) { session.setToken(undefined); setError('Sign-in failed. Please start again.'); } });
    return () => { active = false; };
  }, [auth, router, session]);
  const message = auth ? error || 'Completing sign-in…' : 'Live sign-in is not configured';
  return <main className="main-shell"><section className="panel" role={error || !auth ? 'alert' : 'status'}>{message}</section></main>;
}
