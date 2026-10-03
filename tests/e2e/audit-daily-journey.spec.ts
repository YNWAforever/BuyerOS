// Q09 U09: same UI-created dataset through a real disposable Celery/Valkey transport.
// OIDC/provider/contact/policy inputs remain fictional; this is not live provider verification.
import {test} from '@playwright/test';
import {registerStaffJourney} from './fixtures/staff-journey';
test.describe('Q09 U09',()=>registerStaffJourney('celery'));
