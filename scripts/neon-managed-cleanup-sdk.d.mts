import type {Server} from 'node:http';
import type {RealRunJournal} from './neon-real-preflight.mjs';
import type {FixtureExecutionBoundary} from './neon-execution-boundary.mjs';
export interface ManagedFixtureCleanupResult {complete:boolean;blocked:string|null;absent_identity:boolean;receipts:string[];fixture_only:true;external_verified:false;}
export function runFixtureManagedIdentityCleanup(options:{execution:FixtureExecutionBoundary;journal:RealRunJournal;gateway:Server;nonce:string;sessionCookie:string;now?:()=>number}):Promise<ManagedFixtureCleanupResult>;
