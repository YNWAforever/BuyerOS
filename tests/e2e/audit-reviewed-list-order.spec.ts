import {test} from '@playwright/test';
import {registerWorkbenchStaffJourney as registerStaffJourney} from './fixtures/staff-journey';

test.describe('C61-26 held committed review ack keeps list selection after current read',()=>{
  registerStaffJourney('celery','keyboard',undefined,{delayedReviewAck:true});
});
