# P9 API surface - progress ledger

Plan: docs/buyeros/plans/2026-09-15-p9-api-surface-implementation.md
Branch: p9-api-surface
Base: 456ad93



PRE-FLIGHT CONFLICTS (owner approved fixing the plan first; NOT yet applied)
1. Task 5 approve route must match the contract:
   replace /v1/workspaces/{workspace_id}/projects/{project_id}/icp-versions/{number}/approve
   with    POST /v1/workspaces/{workspace_id}/icp-versions/{icp_version_id}/approve
   -> split the icp router: prefix /v1/workspaces/{workspace_id}; list/save at /projects/{project_id}/icp-versions;
      approve at /icp-versions/{icp_version_id}/approve (UUID path param, not project_id+number).
   -> update the approve handler signature/lookup (fetch IcpVersion by id) and the Task 5 test URLs/assertions.
2. Task 4 readiness must match the contract: drop /health/ready as a contract path.
   -> implement GET /v1/workspaces/{workspace_id}/readiness (+ capabilities) per spec; keep /health/live as a
      non-contract liveness probe only, and note that distinction in the spec/plan.
3. Task 5 list_workspaces raw SQL joins memberships (FORCE RLS) with no app.workspace_id -> always returns 0 rows.
   -> resolve the User by (issuer, subject) first (users is not RLS-protected), then for each candidate workspace
      set the transaction-local tenant context and read memberships; or use a reviewed SECURITY DEFINER function.
4. Task 6 must NOT invent /v1/unimplemented/{operation_id} (violates contract-first / no parallel endpoint).
   -> delete that route; keep UNIMPLEMENTED_OPERATIONS as a registry and return 501 from the declared paths only,
      or omit entirely and document the gap.
5. Task 7 tooling must match the repo (pnpm, not npx): add a devDependency + pnpm script in services/api,
   pin the openapi-typescript version exactly, and record the resolved version; avoid an unpinned network fetch.

RESUME: apply 1-5 to docs/buyeros/plans/2026-09-15-p9-api-surface-implementation.md (and the P9 spec where noted),
regenerate SHA256SUMS, then start Task 1 with subagent-driven-development.
