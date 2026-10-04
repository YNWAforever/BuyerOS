import type {RealRunJournal} from './neon-real-preflight.mjs';
export interface NeonCleanupReadback {method:'GET';url:string;status:number;body:Record<string,unknown>;receivedAt:string;}
export interface NeonCleanupDescriptor {method:'GET'|'DELETE';url:string;body?:string;}
export interface NeonCleanupPlan {
 schema_version:1;target_fingerprint:string;external_authorized:false;external_verified:false;execution_enabled:false;
 blocked:'managed-identity-cleanup-contract-unverified'|'external-transport-and-authority-required'|'unresolved-request-reconciliation-required';
 identity_erasure_verified:false;project_recovery_window_days:7;
 resources:{kind:'auth'|'project';id:string;read:NeonCleanupDescriptor;delete:NeonCleanupDescriptor|null}[];
 requirements:string[];
}
export function planNeonCleanup(options:{journal:RealRunJournal;projectRead:NeonCleanupReadback;authRead:NeonCleanupReadback;now?:number}):NeonCleanupPlan;
