import {getAuth,describeRuntime} from '../../../lib/neon-real-runtime/server';
import {readRealRuntimeConfiguration} from '@/scripts/neon-real-runtime.mjs';
import {assertRuntimeProbeTarget,installProbeFetchGuard} from '@/scripts/neon-runtime-probe.mjs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    if (process.env.N00_RUNTIME_PROBE_MODE !== 'fixture') throw new Error('N00_PROBE_DISABLED');
    const config = readRealRuntimeConfiguration(process.env);
    assertRuntimeProbeTarget(config);
    const guard = installProbeFetchGuard();
    const sdk = getAuth();
    let egressDenied = false;
    if (new URL(request.url).searchParams.get('egress') === 'test') {
      try {await fetch('https://blocked.fixture.invalid/probe');}
      catch (error) {if (!(error instanceof Error) || error.message !== 'N00_PROBE_FETCH_DISABLED') throw error; egressDenied = true;}
    }
    return Response.json({fixture_only: true, ...describeRuntime(),
      sdk_initialized: typeof sdk.handler === 'function' && typeof sdk.getSession === 'function' && typeof sdk.middleware === 'function',
      egress_denied: egressDenied, transport: guard.metrics()});
  } catch (error) {
    const code = error instanceof Error && /^N00_[A-Z_]+$/.test(error.message) ? error.message : 'N00_RUNTIME_PROBE_FAILED';
    return Response.json({fixture_only: true, external_verified: false, code}, {status: 503});
  }
}
