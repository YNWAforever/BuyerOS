import type {Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
const contract=JSON.parse(readFileSync('docs/buyeros/contracts/sales.openapi.yaml','utf8'));
const catalogue=JSON.parse(readFileSync('services/api/buyeros_api/sales/catalogue.json','utf8')).skills;
export const threadId='d1000000-0000-4000-8000-000000000001',otherId='d1000000-0000-4000-8000-000000000002',taskId='d2000000-0000-4000-8000-000000000001',outputId='d3000000-0000-4000-8000-000000000001';
export async function fixture(page:Page,{viewer=false,initial=false,denied=false}={}){
 const requests:{path:string;method:string;body:Record<string,unknown>|null;key?:string}[]=[];
 const thread={id:threadId,title:'Synthetic discussion',version:1,templateId:'custom',access:viewer?'viewer':'owner',shareCount:0,messages:[],sources:[],runs:[],createdAt:1,updatedAt:1};
 let task:Record<string,unknown>|null=initial?{id:taskId,thread_id:threadId,skill_id:'first-project',skill_version:'1',revision:1,state:'ready_for_review',context_digest:null,output_ids:[],pending_review:null,message_sequence:1,intake:[{id:'i',revision:1,user_message:'Synthetic setup',arguments:{offer_description:'Sensors'},source_refs:[]}],arguments:{offer_description:'Sensors'},source_refs:[],missing_inputs:[]}:null;
 let output:Record<string,unknown>|null=null;
 await page.route('**/v1/**',async route=>{
 const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method(),body=req.postData()?req.postDataJSON():null;
 requests.push({path,method,body,key:req.headers()['idempotency-key']});let data:unknown={};let status=200;
 if(path.endsWith('/sales/skills'))data={skills:catalogue.map((s:{id:string})=>{const branch=contract.components.schemas.TaskInput.allOf[0].oneOf.find((v:{properties:{skill_id:{const:string}}})=>v.properties.skill_id.const===s.id);const name=branch.properties.arguments.$ref.split('/').at(-1).replace(/^Intake/,'');return {...s,inputs_schema:contract.components.schemas[name]};})};
 else if(path.endsWith('/conversation-threads'))data=method==='POST'?thread:{items:[thread,{...thread,id:otherId,title:'Second discussion'}],total:2,offset:0,limit:50};
 else if(path.includes('/conversation-threads/'))data=path.endsWith('/share-recipients')?{items:[],total:0}:{...thread,id:path.split('/conversation-threads/')[1].split('/')[0]};
 else if(path.endsWith('/sales-tasks')&&method==='POST'){status=201;task={id:taskId,thread_id:threadId,skill_id:body.skill_id,skill_version:'1',revision:1,state:'needs_input',context_digest:null,output_ids:[],pending_review:null,message_sequence:1,intake:[{id:'i',revision:1,user_message:body.user_message,arguments:body.arguments,source_refs:body.source_refs}],arguments:body.arguments,source_refs:body.source_refs,missing_inputs:['offer_description']};data=task;}
 else if(path.endsWith('/sales-tasks'))data={items:task?[task]:[],total:task?1:0,offset:0,limit:50};
 else if(path.endsWith('/followups')){task={...task,revision:2,state:'ready_for_review',arguments:body.arguments,source_refs:body.source_refs,missing_inputs:[],intake:[...(task?.intake as object[]??[]),{id:'i2',revision:2,user_message:body.user_message,arguments:body.arguments,source_refs:body.source_refs}]};data=task;}
 else if(path.endsWith('/core-preparation')){output={id:outputId,revision:1,visibility:'thread',kind:'project_setup',content:{summary:'Synthetic saved setup',unknowns:[],missing_fields:['unselected_recipient'],next_actions:['Select recipient']},availability:'available',citations:[],dependencies:[],native_refs:[{surface:'buyer',id:otherId,revision:1}]};task={...task,state:'completed',revision:3,output_ids:[outputId]};data=output;}
 else if(path.endsWith('/events'))data={events:[],next_sequence:null};
 else if(path.endsWith('/sales-tasks/capability'))data={admission_enabled:true};
 else if(path.endsWith('/sales-tasks/native-sources'))data={items:[]};
 else if(path.includes('/sales-tasks/'))data=task;
 else if(path.endsWith('/sales-outputs'))data={items:output?[output]:[],total:output?1:0,offset:0,limit:50};
 else if(path.endsWith('/permissions'))data={can_edit:!viewer};
 else if(path.includes('/sales-outputs/'))data=path.endsWith('/versions')?{outputs:output?[output]:[],next_revision:null}:output;
 else if(path.includes('/xverum/tasks/')&&path.endsWith('/stages'))data={items:[]};
 else if(path.endsWith('/xverum/connections'))data={connections:[]};
 else if(path.endsWith('/offer-documents')||path.endsWith('/icp-versions')||path.endsWith('/runs'))data={items:[],total:0,limit:20,offset:0};
 else data={offer_revision:1};
 if(denied&&path.includes('/sales-outputs/'))return route.fulfill({status:403,json:{code:'POLICY_BLOCKED',message:'denied',retryable:false,request_id:'synthetic'}});
 await route.fulfill({status,json:{data,data_mode:'live',request_id:'synthetic'}});
 });return {requests};
}
