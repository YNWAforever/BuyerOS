import {auth} from '../../lib/neon-compatibility/server';
import Client from './client';
export const dynamic='force-dynamic';
export default async function Page(){const {data,error}=await auth.getSession();return <main style={{marginInlineStart:320,padding:24}}><h1>N00 fictional compatibility probe</h1><output data-testid="server-session">{error?'error':data?.user?.id??'anonymous'}</output><Client/></main>;}
