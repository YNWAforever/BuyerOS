import 'server-only';
import {createNeonAuth} from '@neondatabase/auth/next/server';
import {neonAuthHandlers} from './neon-boundary';

// Evaluated on a request, never at build time. Missing/unapproved environments stay closed.
export const neonHandlers=neonAuthHandlers(()=>process.env,config=>createNeonAuth(config).handler());
