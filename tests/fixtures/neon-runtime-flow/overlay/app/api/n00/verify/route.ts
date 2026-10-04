import {describeRuntime} from '../../../../lib/neon-real-runtime/server';
import {verifyWithOwnedDiagnostic} from '@/scripts/neon-real-diagnostic.mjs';
export const dynamic='force-dynamic';
export async function POST(request:Request){try{return await verifyWithOwnedDiagnostic({environment:process.env,description:describeRuntime(),request});}catch{return Response.json({code:'N00_DIAGNOSTIC_NOT_BOUND'},{status:503,headers:{'Cache-Control':'no-store'}});}}
