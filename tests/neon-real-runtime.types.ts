import {createNeonAuth} from '@neondatabase/auth/next/server';
import {createRealAuthRuntime,readRealRuntimeConfiguration} from '../scripts/neon-real-runtime.mjs';
const runtime=createRealAuthRuntime({readEnvironment:()=>process.env,createAuth:createNeonAuth});
const sdk:ReturnType<typeof createNeonAuth>=runtime.getAuth();
void sdk.getSession;
createNeonAuth(readRealRuntimeConfiguration(process.env).sdk);
// @ts-expect-error a concrete SDK instance must not widen to any/number
const notAnSDK:number=runtime.getAuth();
void notAnSDK;
// @ts-expect-error exact EdDSA trust is not an RSA algorithm
const notEdDSA:'RS256'=readRealRuntimeConfiguration(process.env).trust.algorithm;
void notEdDSA;
// @ts-expect-error validated runtime cookie configuration is immutable
readRealRuntimeConfiguration(process.env).sdk.cookies.secret='changed';
