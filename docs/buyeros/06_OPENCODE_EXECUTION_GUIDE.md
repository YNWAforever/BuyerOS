# OpenCode execution guide

This package is an implementation handoff, not an automatic execution configuration. Planning is complete only as documentation; no implementation task is complete or approved by producing this pack. Read the [task manifest](tasks/index.json), [decisions](00_README_AND_DECISIONS.md), and [progress template](handoff/PROGRESS.template.md).

## 1. Verified tool status and documentation

The planning environment's `command -v opencode` found no executable in PATH. `opencode --version` is **NOT RUN**. This does not establish whether OpenCode exists on the owner's implementation machine. Version-dependent configuration, CLI agent flags, model IDs, permission JSON, and native task execution are deliberately not supplied.

The official OpenCode documentation was consulted on 2026-09-14 UTC. It describes Plan and Build agents, instruction loading through AGENTS files, permission controls, and CLI operation. Use its current documentation only after verifying the installed runtime. [Agents](https://opencode.ai/docs/agents/), [rules](https://opencode.ai/docs/rules/), [permissions](https://opencode.ai/docs/permissions/), [CLI](https://opencode.ai/docs/cli/).

Use Plan to review one selected task. Use Build only after explicit owner approval of that task and its concrete reviewed scope. A mode label alone is not a security boundary: tool permissions, file scope, and human approvals still apply. Do not invent model identifiers for “Astra 6”; use the actual available model selected in the owner's environment.

The [AGENTS addendum](handoff/AGENTS.addendum.proposed.md) is a proposal inside this pack. It is not active repository policy until separately reviewed and applied. Never overwrite existing `AGENTS.md`, active OpenCode config, access controls, or repository instructions to make work easier. No allow-all permissions, automatic approval flags, or unreviewed executable agent configuration are part of this handoff.

## 2. First task and approval boundary

Start with **BO-000** in Plan. Its initial status is `READY_FOR_REVIEW`, meaning ready to inspect, not authorized to implement. Read the task's actual filename from `tasks/index.json`; do not guess it. Recheck the current repository because commits may have changed after planning.

Expected target: `YNWAforever/BuyerOS` (canonical; planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; the source import is still pending). The audited content baseline is `YNWAforever/buyerosgpt`. The source audit observed GitHub commit `b804ba8d1514a1049b7202c861278dd72c473a75` and Sites export commit `76892126c86031bfe8e7ab517adba7f306040313`, with matching tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Different histories can share content; do not force one commit onto the other. The saved Site is `appgprj_6aa82285e5108191aac9c44c840c5efe`, URL `https://fimmick-buyeros.laichiwillyjp.chatgpt.site`.

BO-000 should return: exact source and working-tree state; applicable instructions; current installed OpenCode version; reference/access gaps; preserved route/component baseline; differences from this pack; whether BO-001 is eligible for review. If safety-critical material differs, revise the task/decision documents in the scope approved for documentation; do not improvise application changes. Missing historical research/projection/register is B-INPUTS, to be supplied or explicitly dispositioned by the owner before depending on those claims.

Approval record must identify task ID, plan revision, reviewed source baseline, allowed files/actions, approver, date/time, constraints, and separately authorized environment/provider spend if any. Approval to implement code with deterministic fixtures does not imply cloud provisioning, production migration, paid live calls, deploy, push, or email delivery. Prior session approvals remain authoritative only for their actual scope; do not seek repetitive permission for already approved reversible work.

## 3. Read and compare before each task

1. Read the repository's applicable ancestor/root/nested instructions and relevant handoff files. Do not assume the audit's “no AGENTS found” remains true.
2. Capture repository identity, branch/HEAD, `git status --short`, and relevant diffs without revealing secrets. Preserve unrelated dirty files. If a required file contains newer edits, inspect and integrate safely; never reset it to the plan's historical content.
3. Read documents 00, 02, 03, the selected task, its contract references, dependency completion evidence, and latest progress. Read document 05 for relevant negative tests and release gates.
4. Verify required existing files and exact symbols still exist. All new paths are PROPOSED until created in an approved implementation task. This source uses root `app/`, `features/`, `services/`; do not add a parallel `src/` application because the older specification used illustrative paths.
5. Confirm unresolved blockers, licenses, provider guarantees, budgets, identity, and migration ownership. A missing dependency or BLOCKED task cannot be skipped merely because its UI is already present.
6. In Plan, state exact changes, contract/migration impact, side effects, focused verification commands, expected result, rollback/roll-forward, and residual risk. Return the concrete scope for approval. Do not run paid checks to discover whether a provider supports an API.

## 4. Build only the explicitly approved task

After approval, select Build in the verified runtime and use a task-specific prompt. Configure any required permissions only through version-verified supported controls after approval. Scope filesystem edits to the task's existing/proposed files and explicitly listed `dependency_output_files_to_modify`. The latter are PROPOSED at audit time and must exist as verified predecessor outputs before modification; they are not permission to invent a parallel module. Approve command capabilities narrowly; do not give wildcard access to arbitrary shell, network, destructive git, deployment, or cloud actions.

Preserve Vinext/React/TypeScript, its App Router conventions, pnpm and lockfile, UI tokens/components, English/zh-HK dictionaries, and account-first journey. Keep FastAPI as sole proposed domain API, Alembic as sole domain migration owner, and Celery/Valkey as the one proposed durable queue. Architecture changes require an ADR/task revision. No provider or tenant credential belongs in browser code, fixtures, logs, or progress documents.

Implement the selected vertical slice and its negative tests only. Consult exact inspected upstream paths/commits and license decisions before copying code. GPL subprocess isolation is not license clearance. Do not enable the deferred OpenOutFind integration or delivery just because upstream supports it.

Run the relevant reviewed tests in a disposable environment. Inspect install/build/test scripts and lifecycle hooks before execution; deny paid provider and mailbox egress by default. Use deterministic fixtures with `.example` identities. Do not weaken a failing security test, change data to force a green result, or silently fall back to demo when live APIs fail. Record pre-existing failures separately from regressions. Any live smoke test requires its own bounded authorized task.

Do not commit, push, migrate a real database, provision infrastructure, deploy, publish, change Site access, purchase contacts, connect mailboxes, or send messages unless that exact action is explicitly authorized. Task code approval alone does not activate external services. This planning session authorizes none of those actions.

## 5. Manifest, dependencies, and parallelism

`tasks/index.json` and task YAML are **our handoff convention**, not an assumed native OpenCode execution engine. Read them manually or with separately reviewed tooling; do not infer that OpenCode schedules or enforces dependencies. The initial DAG expresses prerequisites, not permission.

Allowed lifecycle: `BLOCKED` → `READY_FOR_REVIEW` when objective blockers/dependencies have evidence; → `APPROVED_READY` after explicit selected-task approval; → `IN_PROGRESS` during that implementation; → `DONE` only after its acceptance evidence and review are recorded. A parent phase cannot mark child tasks complete by assertion. BO-029 requires live-pilot approval independently; BO-030 is a separately approved P7 design with no automatic delivery implementation.

Parallel work is limited to tasks with disjoint files, schema ownership, and contracts. Serialize migrations, shared contracts, budget/policy core, and frontend integration points. `features/workspace.tsx` contains multiple screens; seemingly different UI tasks may conflict there and should be sequenced. Record shared-file ownership before parallel execution. Merge conflicts require comparison with both authors' intended changes, not wholesale replacement.

## 6. Stop and replan rules

Stop the affected task, preserve a safe diff, and record the blocker if:

- The repository, framework/router, deployment surface, contract, or required source differs materially.
- Identity/tenant guarantees or non-owner database isolation cannot be established.
- A provider has no verified bounded cost, idempotency/status/reconciliation path, permitted use, or required capability.
- License obligations differ from the pinned review, or proposed reuse would introduce unresolved GPL obligations.
- A migration would be destructive, a second schema owner appears, or a rollback would discard charged operations.
- Current logic conflates fit, human acceptance, contact validity, suppression, lookup policy, outreach policy, content approval, or delivery.
- Unexpected external writes, real personal data in fixtures/logs, secret exposure, or sending capability appears.

Replanning output must state the source difference, impact on objective/tests, proposed ADR/task change, affected dependency IDs, and smallest required decision. Keep independent authorized work moving where possible. Do not add an architecture workaround solely to evade a blocker.

## 7. Completion and resume evidence

Update the progress file from [PROGRESS.template.md](handoff/PROGRESS.template.md) with changed files/symbols, exact commands/exit status, test artifacts, current commit/diff, migrations proposed/executed, policy/financial invariants checked, known risks, and next eligible review. State **NOT RUN** with reason for every unexecuted required check. Never mark a task DONE because it compiles while its concurrency, tenant, or policy acceptance tests remain missing.

On a new session or after context compaction: read applicable instructions, latest progress, selected task, current source diff, and contract/ADR changes in that order. Revalidate approval scope and dependency evidence. Resume the documented next step; do not rebuild decisions from conversational memory or silently broaden the task.

Final task report should contain objective achieved, concrete diff, relevant results and failures, residual blockers, rollback/roll-forward, and next review. Separate code complete from released: a verified fixture implementation is not a live pilot, and an approved draft is not delivered.

## 8. Exact first starter prompt

The canonical copy-paste prompt is [OPENCODE_START_PROMPT.md](handoff/OPENCODE_START_PROMPT.md). Its first instruction is Plan-only BO-000 review. Do not switch to Build automatically after reviewing it.
