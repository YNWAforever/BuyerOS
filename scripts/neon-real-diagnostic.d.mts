import type {RealRuntimeEnvironment,RealRuntimeDescription} from './neon-real-runtime.mjs';
export function verifyWithOwnedDiagnostic(options:{environment:RealRuntimeEnvironment;description:Pick<RealRuntimeDescription,'fingerprint'|'external_verified'>;request:Request;fetch?:typeof fetch}):Promise<Response>;
export function validDiagnosticReceipt(value:unknown,expected:{fingerprint:string;subject:string}):boolean;
