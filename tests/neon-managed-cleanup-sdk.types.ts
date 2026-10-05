import type {ManagedFixtureCleanupResult} from '../scripts/neon-managed-cleanup-sdk.mjs';
import {runFixtureManagedIdentityCleanup} from '../scripts/neon-managed-cleanup-sdk.mjs';
// @ts-expect-error cleanup requires a branded runtime boundary, owned gateway and journal
void runFixtureManagedIdentityCleanup({sessionCookie:'fictional-cleanup-admin=owned'});
declare const result:ManagedFixtureCleanupResult;
// @ts-expect-error a local fixture cannot claim external verification
const external:true=result.external_verified;
void external;
