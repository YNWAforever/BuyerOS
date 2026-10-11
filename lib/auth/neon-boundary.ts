import {loadNeonConfig} from './neon-config';
type Context={params:Promise<{path:string[]}>};
type Handler=(request:Request,context:Context)=>Promise<Response>;
type Handlers={GET:Handler;POST:Handler};
type SdkConfig={baseUrl:string;cookies:{secret:string;sameSite:'lax';sessionDataTtl:number};logLevel:'silent'};
type Factory=(config:SdkConfig)=>Handlers|Promise<Handlers>;
const failure=(status:number)=>Response.json({code:status===503?'AUTH_UNAVAILABLE':status===403?'AUTH_FORBIDDEN':'NOT_FOUND'},{status,headers:{'cache-control':'no-store'}});
/** Only the dedicated auth route receives cookies. The public SDK owns protocol/session state. */
export function neonAuthHandlers(environment:()=>Record<string,string|undefined>,factory:Factory):Handlers {
  let cached:{key:string;handlers:Promise<Handlers>}|null=null;
  const handle=(method:'GET'|'POST'):Handler=>async(request,context)=>{
    try{
      const env=environment();if(env.BUYEROS_NEON_AUTH_ROUTE_ENABLED!=='1')return failure(503);
      const config=loadNeonConfig(env),target=new URL(request.url);
      if(!target.pathname.startsWith('/api/auth/'))return failure(404);
      if(target.origin!==config.publicOrigin)return failure(403);
      const origin=request.headers.get('origin');
      if(origin&&origin!==config.publicOrigin||method==='POST'&&!origin)return failure(403);
      const sdkConfig:SdkConfig={baseUrl:config.authUrl,cookies:{secret:config.cookieSecret,sameSite:'lax',sessionDataTtl:300},logLevel:'silent'};
      const key=JSON.stringify(sdkConfig);
      if(cached?.key!==key){const handlers=Promise.resolve().then(()=>factory(sdkConfig));cached={key,handlers};handlers.catch(()=>{if(cached?.handlers===handlers)cached=null;});}
      const handlers=await cached.handlers,response=await handlers[method](request,context);
      const headers=new Headers(response.headers);headers.set('cache-control','no-store');
      return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
    }catch{return failure(503);}
  };
  return {GET:handle('GET'),POST:handle('POST')};
}
