import {expect,test} from '@playwright/test';
import {createHash} from 'node:crypto';
import {registerWorkbenchStaffJourney as registerStaffJourney,type StaffJourneyReadback} from './fixtures/staff-journey';
import {observeJoinedPages,joinedReadback} from './fixtures/c61-joined-readback';
test.beforeEach(observeJoinedPages);
async function unicodeReadback(context:StaffJourneyReadback){
 const response=await context.request.get(`http://127.0.0.1:8000/v1/workspaces/${context.workspace}/drafts/${context.draftId}`,{headers:{Authorization:'Bearer fixture-reviewer'}});
 expect(response.status()).toBe(200);const draft=(await response.json()).data;
 expect(draft.subject).toBe('😀 Keyboard invitation é');expect(draft.body).toContain('👩‍💻 é');expect(draft.revision_number).toBe(3);
 expect(draft.grounding_review.reviewed_by).toBe('e0000000-0000-4000-8000-000000000004');
 const receipt=context.groundingReceipt!;expect(receipt.committed_status).toBe(200);expect(receipt.requests).toHaveLength(2);expect(receipt.requests[1]).toEqual(receipt.requests[0]);
 const submission=receipt.requests[0].body;expect(submission.revision_id).toBe(draft.grounding_review.based_on_revision_id);expect(submission.content_hash).toBe(draft.grounding_review.based_on_content_hash);expect(draft.revision_id).not.toBe(submission.revision_id);
 expect(submission.segments[0]).toMatchObject({field:'subject',start:0,end:1,exact_text:'😀',classification:'non_factual'});
 expect(submission.segments[1]).toMatchObject({field:'subject',start:1,end:Array.from(draft.subject as string).length,exact_text:(draft.subject as string).slice(2)});
 expect(draft.grounding_review.segments).toEqual(submission.segments);expect(submission.segments).toHaveLength(6);
 for(const segment of submission.segments)expect(Array.from(draft[segment.field] as string).slice(segment.start,segment.end).join('')).toBe(segment.exact_text);
 const exactCopy=context.approvedCopy.split('\nSubject: ')[1].split('\n\nSources: ')[0];expect(exactCopy).toBe(draft.subject+'\n\n'+draft.body);
 await joinedReadback(context,{actual_utf16_selection:[0,2],exact_server_codepoint_range:[0,1],approved_revision_id:draft.revision_id,approved_content_hash:draft.content_hash,grounding_receipt:receipt,approved_copy_sha256:createHash('sha256').update(context.approvedCopy).digest('hex'),exact_unicode_copy_verified:true});
}
test.describe('C61-26 owned joined Unicode exact-revision fixture',()=>registerStaffJourney('celery','keyboard',unicodeReadback,{unicode:true,loseGroundingAck:true}));
