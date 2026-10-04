import type {RealRuntimeConfiguration} from './neon-real-runtime.mjs';
export function installFlowFixtureTransport(config: RealRuntimeConfiguration, host?: {fetch: typeof fetch},diagnosticNonce?:string|null): Readonly<{metrics:()=>Readonly<{fixture_only:true;blocked:number;forwarded:number;diagnostic:number;external_requests:0}>}>;
