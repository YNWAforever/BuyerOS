# PROPOSED BuyerOS AGENTS addendum — inactive

This document is a review proposal. Do not overwrite or activate it as `AGENTS.md` during planning. Reconcile it with current ancestor/root/nested repository instructions and apply only after explicit approval of the configuration change.

## Scope and product

Target only the verified `YNWAforever/BuyerOS` source (audited baseline `YNWAforever/buyerosgpt` commit b804ba8d1514a1049b7202c861278dd72c473a75 imported at tree `b4c6b538` and merged via `72fef7d`) linked to Site `appgprj_6aa82285e5108191aac9c44c840c5efe`. Preserve unrelated work, approved assets, routes, Vinext/React/TypeScript runtime, pnpm lockfile, English/zh-HK, and the existing table/drawer/draft workspace.

Preserve: Offer → approved buyer profile → discovery → evidence → human acceptance → optional permitted business-contact lookup → grounded draft → human approval → outcomes. A company is distinct from its contacts and project-specific fit/review. Fit, acceptance, contact validity, suppression, contact-research permission, outreach permission, draft approval, and delivery status are independent.

## Task execution

- Read `docs/buyeros/00_README_AND_DECISIONS.md`, current contracts, selected task, dependency evidence, latest progress, and applicable instructions before changes.
- Review in Plan first. Build only the explicitly approved task/revision/scope. The task manifest is a handoff convention, not native automated execution.
- Check current commit/diff and exact source symbols. Preserve dirty/unrelated edits. New paths remain PROPOSED until created by an approved task.
- Use only version-verified OpenCode capabilities and actual available model identifiers. No allow-all permissions or configuration that bypasses review. Configuration changes remain separately reviewed proposals.
- Execute reviewed tests in a disposable environment with deterministic providers and denied paid/mail egress. Inspect scripts/install hooks before running. Report actual commands/results and **NOT RUN** checks honestly.
- Update progress with source/diff, scope, tests, blockers, contract/migration changes, approval evidence, and next eligible task. Do not mark incomplete safety tests complete.

## Mandatory implementation invariants

- The API independently verifies identity, tenant membership, role, policy, suppression, state preconditions, and budget. Browser checks are presentation only.
- Use one domain API and one migration owner per approved architecture. Do not create parallel Node domain logic or Drizzle/Alembic migration ownership for the same domain tables.
- Paid discovery, LLM, and contact calls require atomic bounded reservations. Unknown/timeout submissions retain holds until authoritative reconciliation; cancellation cannot assume no charge.
- Quote confirmation is tenant-scoped, versioned, expiry-bound and idempotent; revalidate policy/fit/acceptance/suppression at confirmation, dispatch, and appropriate late-result exposure.
- Draft approval binds exact content revision/hash, recipient, offer/ICP/evidence and policy context. Material changes, deletion, suppression, or revoked permission stale approval.
- Export/copy/download respects the same tenant/purpose restrictions as API/UI reads. It never creates a sent event or bypasses blocked contact permission.
- Live failure never returns demo fixtures. Demo state, `.example` data, storage and cost events remain isolated from live tenants.
- Treat uploads, webpages, provider data, and model output as untrusted. Enforce SSRF, parser limits, schema/evidence validation, secret redaction, retention and deletion outside prompts.
- Preserve pinned upstream license notices. Defer unresolved GPL reuse; separate worker/process boundaries do not automatically resolve commercial licensing obligations.

## Stop boundaries

Stop and propose an ADR/task revision for material source/contract/architecture changes, uncertain provider billing, missing tenant isolation, unresolved licensing, or destructive migrations. No replacement application or unrelated repository is an acceptable workaround.

Code approval does not authorize commits, pushes, real migrations, provisioning, deployment, publication, Site access changes, paid calls, contact purchase, mailbox connection, or sending. Perform these only under explicit authorization covering the specific action/environment/budget. MVP-A contains no real delivery; P7 remains separate even after pilot success.
