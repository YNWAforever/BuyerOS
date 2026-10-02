import cleanupDisposableE2eDatabase from '../teardown';
export default async function cleanupCloudflareFixture(){
  // Stop all local Queue/Workflow egress before the owned cluster is removed.
  try{
    const response=await fetch('http://127.0.0.1:8788/fixture/stop',{method:'POST',headers:{'x-buyeros-fixture':'local-only'},signal:AbortSignal.timeout(30_000)});
    if(!response.ok) throw new Error('local Cloudflare runtime teardown failed');
  }catch(error){
    // A failed startup has no controller listener. Other failures retain the DB
    // marker for explicit cleanup rather than removing a still-used database.
    if(!(error instanceof TypeError && error.cause && (error.cause as {code?:string}).code==='ECONNREFUSED')) throw error;
  }
  cleanupDisposableE2eDatabase();
}
