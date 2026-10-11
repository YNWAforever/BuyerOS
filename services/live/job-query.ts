import type {operations} from '@/services/generated/buyeros-api';
export type JobScope={kind:'project';workspaceId:string;projectId:string}|{kind:'workspace';workspaceId:string};
type Query=NonNullable<operations['listAsyncJobs']['parameters']['query']>;
export type JobStatus=NonNullable<Query['status']>;
export type JobQueryOptions={status?:JobStatus;offset:number;limit:number};
const statuses:JobStatus[]=['queued','running','cancel_requested','cancelled','completed','failed'];
export function readJobStatus(value:string|null):JobStatus|undefined{return statuses.find(status=>status===value);}
/** The same canonical filter builds count, page reads and navigation. */
export function buildJobQuery(scope:JobScope,{status,offset,limit}:JobQueryOptions):URLSearchParams{
 if(!scope.workspaceId||scope.kind==='project'&&!scope.projectId)throw new Error('Job scope is required');
 if(!Number.isSafeInteger(offset)||offset<0||!Number.isSafeInteger(limit)||limit<1||limit>100)throw new Error('Invalid job page');
 if(status&&!statuses.includes(status))throw new Error('Invalid job status');
 const query=new URLSearchParams({offset:String(offset),limit:String(limit)});
 if(status)query.set('status',status);
 if(scope.kind==='project')query.set('project_id',scope.projectId);
 return query;
}
export function jobQueryParams(scope:JobScope,options:JobQueryOptions):Query{
 const q=buildJobQuery(scope,options);
 return {offset:Number(q.get('offset')),limit:Number(q.get('limit')),...(q.has('status')?{status:readJobStatus(q.get('status'))}:{}),...(q.has('project_id')?{project_id:q.get('project_id')!}:{})};
}
export function jobScopeLink(scope:JobScope,status?:JobStatus):string{
 const q=buildJobQuery(scope,{status,offset:0,limit:20}),params=new URLSearchParams({workspace:scope.workspaceId,job_scope:scope.kind});
 if(q.has('project_id'))params.set('project',q.get('project_id')!);
 if(q.has('status'))params.set('job_status',q.get('status')!);
 return '/app/operations?'+params;
}
