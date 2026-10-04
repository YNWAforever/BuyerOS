import type {NeonCleanupPlan,NeonCleanupReadback} from '../scripts/neon-cleanup-contracts.mjs';
function strict(plan:NeonCleanupPlan,read:NeonCleanupReadback){
 const disabled:false=plan.execution_enabled;
 const unverified:false=plan.external_verified;
 const unauthorized:false=plan.external_authorized;
 const get:'GET'=read.method;
 // @ts-expect-error A readback cannot be a destructive request.
 const wrongMethod:NeonCleanupReadback={...read,method:'DELETE'};
 // @ts-expect-error A prepared cleanup contract cannot claim live verification.
 const live:NeonCleanupPlan={...plan,external_verified:true};
 // @ts-expect-error Local plans cannot activate execution.
 const armed:NeonCleanupPlan={...plan,execution_enabled:true};
 return {disabled,unverified,unauthorized,get,wrongMethod,live,armed};
}
void strict;
