'use client';
import {useRef, useState} from 'react';
import {Wizard, type Offer} from '@/features/discovery/wizard';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {saveProfile} from '@/services/live/writes';

export function LiveOfferWizard({offer, setOffer, onSaved, t}: {
  offer: Offer; setOffer: (o: Offer) => void; onSaved: (info: {projectId: string; icpVersionId: string}) => void;
  t: (s: string) => string;
}) {
  const {session, client} = useWorkspaceSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // One key per save action, reused across retries so a failed save cannot create a second
  // project; only a successful save retires it, so the next action gets a fresh key.
  const idempotencyKey = useRef<string | null>(null);
  async function save() {
    setBusy(true);
    setError('');
    try {
      if (idempotencyKey.current === null) {
        idempotencyKey.current = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      }
      const out = await saveProfile({client, session, offer, idempotencyKey: idempotencyKey.current});
      idempotencyKey.current = null;
      // Select the saved project in the session seam so the profile panel can load it.
      session.next({project: out.project.id});
      onSaved({projectId: out.project.id, icpVersionId: out.icpVersion.id});
    } catch (err) {
      // A ProfileError names the offending value; a LiveError carries the API code. Neither is
      // swallowed and neither falls back to demo data.
      const failure = err as {message?: string; code?: string};
      setError(failure.code || failure.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      {error ? <p role="alert">{error}</p> : null}
      {busy ? <p role="status">Saving profile...</p> : null}
      <Wizard offer={offer} setOffer={setOffer} run={() => {}} save={save} t={t} />
    </div>
  );
}
