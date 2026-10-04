import 'server-only';
import {createNeonAuth} from '@neondatabase/auth/next/server';
import {createRealAuthRuntime} from '@/scripts/neon-real-runtime.mjs';

// Preparation overlay only: no public BuyerOS route or build-time secrets.
const runtime = createRealAuthRuntime({
  readEnvironment: () => process.env,
  createAuth: createNeonAuth,
});
export const getAuth = runtime.getAuth;
export const describeRuntime = runtime.describe;
