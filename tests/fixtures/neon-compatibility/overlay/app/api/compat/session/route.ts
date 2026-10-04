import {auth} from '../../../../lib/neon-compatibility/server';
export async function GET(){const result=await auth.getSession();return Response.json(result);}
