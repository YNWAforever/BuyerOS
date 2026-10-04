import type {NextRequest} from 'next/server';
import {getAuth} from './lib/neon-real-runtime/server';

export default function proxy(request: NextRequest) {
  return getAuth().middleware({loginUrl: '/auth/sign-in'})(request);
}
export const config = {matcher: ['/compat/return']};
