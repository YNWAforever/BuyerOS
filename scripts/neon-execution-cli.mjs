/** Fixed local fixture helper, not neonctl or a provider credential runner. */
const keys=new Set(['PATH','Path','SystemRoot','SYSTEMROOT','TEMP','TMP','COMSPEC','PATHEXT','USERPROFILE','LOCALAPPDATA','BUYEROS_STRICT_INTEGRATION','WRANGLER_SEND_METRICS','WRANGLER_WRITE_LOGS','CLOUDFLARE_CF_FETCH_ENABLED','N00_FIXTURE_CLI_URL','N00_FIXTURE_CLI_NONCE',
// Windows CreateProcess adds these system metadata fields even with an explicit env.
'HOMEDRIVE','HOMEPATH','LOGONSERVER','SYSTEMDRIVE','USERDOMAIN','USERNAME','WINDIR']);
try{
 if(!Object.keys(process.env).every(key=>keys.has(key)))throw new Error('environment');
 const url=new URL(process.env.N00_FIXTURE_CLI_URL);if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw new Error('owner');
 let body='',size=0;for await(const chunk of process.stdin){size+=chunk.length;if(size>32768)throw new Error('body');body+=chunk;}const input=JSON.parse(body);if(input.channel!=='cli')throw new Error('channel');
 const response=await fetch(new URL('/dispatch',url),{method:'POST',headers:{'Content-Type':'application/json','x-n00-owner':process.env.N00_FIXTURE_CLI_NONCE},body,redirect:'manual',signal:AbortSignal.timeout(3000)});if(response.status!==200)throw new Error('gateway');const result=await response.json();process.stdout.write(JSON.stringify({...result,environment_clean:true}));
}catch{process.stderr.write('N00_EXECUTION_CLI_REFUSED\n');process.exitCode=1;}
