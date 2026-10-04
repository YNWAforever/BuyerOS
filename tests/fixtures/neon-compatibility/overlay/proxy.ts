// N00 overlay only: official SDK middleware consumes the managed session verifier.
import {auth} from './lib/neon-compatibility/server';
export default auth.middleware({loginUrl:'/auth/sign-in'});
export const config={matcher:['/compat/return']};
