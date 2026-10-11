import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {buildJobQuery,jobScopeLink,jobQueryParams,readJobStatus}=await loadModule('services/live/job-query.ts');
const project={kind:'project',workspaceId:'workspace-a',projectId:'project-a'},workspace={kind:'workspace',workspaceId:'workspace-a'};
test('U15 project failed count and paged list preserve identical canonical filter',()=>{
 const count=buildJobQuery(project,{status:'failed',offset:0,limit:1}),list=buildJobQuery(project,{status:'failed',offset:20,limit:20});
 assert.equal(count.get('project_id'),'project-a');assert.equal(list.get('project_id'),count.get('project_id'));assert.equal(list.get('status'),count.get('status'));assert.deepEqual(jobQueryParams(project,{status:'failed',offset:20,limit:20}),{status:'failed',project_id:'project-a',offset:20,limit:20});
});
test('U15 explicit workspace omits project, deep link retains selected scope and status',()=>{
 assert.equal(buildJobQuery(workspace,{status:'failed',offset:0,limit:20}).has('project_id'),false);
 for(const scope of [project,workspace]){const link=new URL(jobScopeLink(scope,'failed'),'http://fixture.test');assert.equal(link.searchParams.get('workspace'),'workspace-a');assert.equal(link.searchParams.get('job_scope'),scope.kind);assert.equal(link.searchParams.get('job_status'),'failed');assert.equal(link.searchParams.get('project'),scope.kind==='project'?'project-a':null);}
});
test('U15 invalid URL status cannot introduce unsupported server filter; paging stays bounded',()=>{
 assert.equal(readJobStatus('invented'),undefined);assert.equal(readJobStatus('failed'),'failed');
 for(const options of [{offset:-1,limit:20},{offset:0,limit:101},{offset:0,limit:0},{offset:0.5,limit:20},{status:'invented',offset:0,limit:20}])assert.throws(()=>buildJobQuery(project,options));
 assert.throws(()=>buildJobQuery({...project,projectId:''},{offset:0,limit:20}));
});
