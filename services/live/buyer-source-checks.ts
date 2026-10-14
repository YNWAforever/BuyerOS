import type {LiveClient} from './client';
import type {SessionScope} from './session';

export type LiveBuyerSourceCheckGrade = 'A'|'B'|'C';

export interface LiveBuyerSourceReference {
  title:string;
  url:string;
}

export interface LiveBuyerSourceCheckInput {
  checkedOn:string;
  grade:LiveBuyerSourceCheckGrade;
  rationale:string;
  limitations:string|null;
  references:LiveBuyerSourceReference[];
}

export interface LiveBuyerSourceCheck extends LiveBuyerSourceCheckInput {
  id:string;
  recordedBy:string;
  createdAt:string;
}

function object(value:unknown):Record<string,unknown>{
  if(typeof value!=='object'||value===null||Array.isArray(value))throw new Error('Invalid source check response');
  return value as Record<string,unknown>;
}

function requiredString(row:Record<string,unknown>,key:string):string{
  const value=row[key];
  if(typeof value!=='string')throw new Error('Invalid source check response');
  return value;
}

function mapSourceCheck(value:unknown):LiveBuyerSourceCheck{
  const row=object(value),grade=row.grade;
  if(grade!=='A'&&grade!=='B'&&grade!=='C')throw new Error('Invalid source check grade');
  if(!Array.isArray(row.sources))throw new Error('Invalid source check references');
  const references=row.sources.map(source=>{
    const item=object(source);
    return {title:requiredString(item,'title'),url:requiredString(item,'url')};
  });
  const limitations=row.limitations;
  if(limitations!==null&&typeof limitations!=='string')throw new Error('Invalid source check limitations');
  return {
    id:requiredString(row,'id'),checkedOn:requiredString(row,'checked_on'),grade,
    rationale:requiredString(row,'rationale'),limitations,references,
    recordedBy:requiredString(row,'recorded_by_user_id'),createdAt:requiredString(row,'created_at'),
  };
}

function sourceChecksPath(workspace:string,buyerId:string):string{
  return `/v1/workspaces/${encodeURIComponent(workspace)}/buyers/${encodeURIComponent(buyerId)}/source-checks`;
}

export async function listBuyerSourceChecks(
  client:LiveClient,session:SessionScope,buyerId:string,signal?:AbortSignal,
):Promise<LiveBuyerSourceCheck[]>{
  const workspace=session.current().workspace;
  if(!workspace)return [];
  const identity=session.identity(),token=session.token(),path=sourceChecksPath(workspace,buyerId);
  const checks:LiveBuyerSourceCheck[]=[];
  const limit=100;
  for(let offset=0;;){
    const data=object(await client.request<unknown>({
      path:`${path}?offset=${offset}&limit=${limit}`,token,scope:identity,signal,
    }));
    const items=data.items,total=data.total;
    if(!Array.isArray(items)||typeof total!=='number'||!Number.isSafeInteger(total)||total<0){
      throw new Error('Invalid source check page');
    }
    checks.push(...items.map(mapSourceCheck));
    if(checks.length>=total)return checks;
    if(items.length===0)throw new Error('Source check page incomplete');
    offset+=items.length;
  }
}

export async function createBuyerSourceCheck(
  client:LiveClient,session:SessionScope,buyerId:string,input:LiveBuyerSourceCheckInput,
  idempotencyKey:string,signal?:AbortSignal,
):Promise<LiveBuyerSourceCheck>{
  const workspace=session.current().workspace;
  if(!workspace)throw new Error('Workspace required for source check');
  const response=await client.request<unknown>({
    path:sourceChecksPath(workspace,buyerId),method:'POST',token:session.token(),scope:session.identity(),
    idempotencyKey,signal,body:{
      checked_on:input.checkedOn,grade:input.grade,rationale:input.rationale,
      limitations:input.limitations,sources:input.references.map(reference=>({title:reference.title,url:reference.url})),
    },
  });
  return mapSourceCheck(response);
}
