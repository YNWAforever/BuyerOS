import 'server-only';
import {createNeonAuth} from '@neondatabase/auth/next/server';
import {createRealAuthRuntime,readRealRuntimeConfiguration} from '@/scripts/neon-real-runtime.mjs';
import {installFlowFixtureTransport} from '@/scripts/neon-runtime-flow-transport.mjs';
// Fixture-only second overlay. Real-only UI/server overlay contains no fictional login.
const runtime=createRealAuthRuntime({readEnvironment:()=>process.env,createAuth:createNeonAuth});
export function getAuth(){const config=readRealRuntimeConfiguration(process.env);if(process.env.N00_FLOW_FIXTURE!=='yes')throw new Error('N00_FLOW_FIXTURE_REQUIRED');installFlowFixtureTransport(config,globalThis,process.env.N00_DIAGNOSTIC_NONCE);return runtime.getAuth();}
export const describeRuntime=runtime.describe;
