import {test} from '@playwright/test';
import {registerStaffJourney} from './fixtures/staff-journey';
import {observeJoinedPages,joinedReadback} from './fixtures/c61-joined-readback';
test.beforeEach(observeJoinedPages);
test.describe('C61-26 owned built eight-module fixture',()=>registerStaffJourney('celery','pointer',joinedReadback));
