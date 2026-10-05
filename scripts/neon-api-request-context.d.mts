import type {Server} from 'node:http';
import type {ExecutionRequest,ExecutionReceipt,FixtureExecutionBoundary} from './neon-execution-boundary.mjs';
import type {RealRunJournal} from './neon-real-preflight.mjs';
export type FixtureApiRequest=Omit<ExecutionRequest,'channel'|'method'>&{method:'GET'|'HEAD'|'POST'};
export interface FixtureApiRequestContext {dispatch(input:FixtureApiRequest):Promise<ExecutionReceipt>;dispose():Promise<{fixture_only:true;external_verified:false;owned_context_disposed:true}>;}
/** Own standalone fictional context; no arbitrary native/parent/browser OS containment. */
export function createFixtureApiRequestContext(options:{gateway:Server;execution:FixtureExecutionBoundary;journal:RealRunJournal;nonce:string;timeoutMs?:number}):Promise<FixtureApiRequestContext>;
