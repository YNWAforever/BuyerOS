import 'server-only';
import {createNeonAuth} from '@neondatabase/auth/next/server';
// N00 ONLY: this file overlays a disposable source copy. Never a real tenant.
export const auth=createNeonAuth({baseUrl:'http://127.0.0.1:44891/fixture/auth',
 cookies:{secret:'fictional-N00-cookie-secret-32-plus-characters',sameSite:'lax',sessionDataTtl:300}});
