# C61-21 current project work queue

The existing Overview has six cards but only failed jobs have a server count.
Pending approvals and unknown acceptance currently open unfiltered Operations.

The new summary reuses buyer selection, draft current-revision selection,
actor-bound AsyncJob and provider receipt list predicates. All six counts and
as_of come from one aggregate statement. Queries use the current canonical
identity, active DB membership, workspace/project and ordinary runtime RLS.
GET summary and provider pages reuse the existing REPEATABLE READ / READ ONLY
transaction helper and set workspace context locally. Rate admission stays separate.
The provider total/page keep one snapshot during concurrent receipt insertion.

The plan file map expands to app registration, roles, OpenAPI/generated types,
draft list filter and provider receipt projection because typed list filters
must exist before frontend links. ProviderOperation.job_id points to
EnrichmentJob, not AsyncJob. Contact receipts scope through their actual quote;
a present buyer must agree with that project. Research receipts scope through
the durable operation reservation's project and run allocations and the run's
canonical actor snapshot. Unknown/submitting are uncertain acceptance; accepted
is known acceptance and is excluded. No network retry or reconciliation occurs.

Missing legacy scope cannot inherit a selected project or actor. Such rows are
excluded from this project list, and C61-19 must validate every admitted live
provider intent's durable scope before research release acceptance. The count
describes visible scoped receipts, never all workspace or provider activity.
The read page exposes IDs, capability, status and timestamps only; account,
input hashes, provider refs and payloads stay private. No RLS/grant widening.

Pending means persisted review_requested, using the same current-revision join
as listDrafts. Opening a draft still revalidates the exact review context and
approval prerequisites; the summary cannot confer approval or semantic truth.

Rollback: revert UI navigation if required, retain compatible read endpoints.
No migration, business history, UUID/FK or provider hold changes are involved.
