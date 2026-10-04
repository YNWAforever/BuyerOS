import type {Server} from 'node:http';
import type {RealRunJournal} from './neon-real-preflight.mjs';
export interface ExecutionRequest {channel:'sdk'|'browser'|'cli'|'control';method:'GET'|'HEAD'|'POST'|'DELETE';path:string;body?:string;headers?:HeadersInit;}
export interface ExecutionReceipt {status:number;body:string;location:string|null;outcome:'accepted'|'rejected'|'unknown';headers:[string,string][];evidenceRef:string;fixture_only:true;external_verified:false;}
export interface FixtureExecutionBoundary {dispatch(input:ExecutionRequest):Promise<ExecutionReceipt>;holds(input:ExecutionRequest):boolean;report():{fixture_only:true;external_verified:false;arbitrary_cli_contained:false;real_provider_traffic_contained:false;journal:ReturnType<RealRunJournal['snapshot']>};}
export function createFixtureExecutionBoundary(options:{backend:Server;journal:RealRunJournal;now?:()=>number;timeoutMs?:number}):FixtureExecutionBoundary;
export function assertFixtureExecutionBoundary(execution:FixtureExecutionBoundary,journal:RealRunJournal):void;
export function createFixtureExecutionGateway(options:{execution:FixtureExecutionBoundary;nonce:string}):Server;
export function runFixtureCli(options:{gateway:Server;nonce:string;request:ExecutionRequest;parentEnvironment?:NodeJS.ProcessEnv}):Promise<ExecutionReceipt&{environment_clean:true}>;
