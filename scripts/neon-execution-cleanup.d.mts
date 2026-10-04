import type {RealRunJournal} from './neon-real-preflight.mjs';
import type {FixtureExecutionBoundary} from './neon-execution-boundary.mjs';
export function runFixtureCleanup(options:{execution:FixtureExecutionBoundary;journal:RealRunJournal;now?:()=>number}):Promise<{complete:boolean;blocked:string|null;absent:string[];receipts:string[];fixture_only:true;external_verified:false}>;
