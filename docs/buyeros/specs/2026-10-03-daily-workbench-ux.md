# Q09 daily workbench UX acceptance

Source: frozen 2026-10-03 plan Q09, F14/F04, cases U09-U12/WF01/WF02. Existing Vinext/React routes, FastAPI authority, generated contracts and visual system remain authoritative. This is local repair execution; no production/auth/provider/delivery activation.

## Five repeatable staff tasks

| Task | Start and success | Failure/recovery | Baseline evidence |
|---|---|---|---|
| 1 Offer and profile | Operator creates/edits offer; reviewer approves exact current ICP | Project committed then ICP fails: keep all fields; same action/key retries; one project. Old approval after offer edit:412, no research | Source ActionIntent exists; unbounded history read reproduced by new browser regression; WF01/WF02 current isolated tests required |
| 2 Research and review | Approved profile; bounded target/cap; research result; reviewer opens evidence and reviews buyer | Unknown acceptance retains exact intent/hold; existing runs queried; rejected role cannot start/review | Q04/Q05 local predecessor evidence; real provider not verified |
| 3 Assign across pages | Selection remains explicit across pages; name-based owner choice; exact confirmation; conflicts visible; retry failed only | No selection: hide selection-dependent forms. Frozen unknown request retained. Q08 all-matching maintenance stays independently accessible | Q05/Q08 fixture proof; employee timing not available |
| 4 Draft to export/outcome | Grounded manual draft; dirty guard; reviewer exact approval; authorized copy/download; staff logs outcome | Save/Discard/Cancel;412/error retains edits; no send. Corrections append history, never replace original | Q12/Q15 fixture evidence; full journey to be tested in Q09 |
| 5 Members and failed job | Admin finds existing verified member and changes role with reason; project failed-job count opens same list | Non-admin denied directory; last admin retained; slow old-scope replies ignored; current role enforced | Q02/Q14 fixture proof; no production membership action |

## Module layout and states

| Module | Layout | Empty | Loading | Error/recovery | Permission |
|---|---|---|---|---|---|
| Overview | Scope selectors once, current project name, next-action queue, metrics | No project/profile offers create/select | Bounded count/metadata read, no stale prior scope | Unavailable plus retry/navigation, no synthetic count | Current membership only; viewer reads |
| Offer | Four existing steps, one active form, document details | Required offer/market/buyer fields | Project plus bounded latest ICP metadata | Partial save preserves form; same key retry; error receives focus | Operator/reviewer/admin edit; viewer read |
| Profile | Current exact revision, paged immutable history, evidence details | No saved profile | Bounded latest/read and history pages | Stale basis/412 explains refresh, no stale approval | Reviewer/admin approval only |
| Research | Target/cap and real paged runs; stable concise status | No runs; approval prerequisite | One summary/status announcement, technical stream counters in details | Unknown intent same-key reconcile; safe retry only when authoritative | Operator/reviewer/admin bounded admission |
| Buyers/lists | Primary buyer list and evidence drawer; filters once; sticky selection summary only when count>0; batch forms disclosed deliberately | No matching snapshot | Snapshot then real pages, no demo fallback | Retry read; row failures visible; frozen scope/selection retained | Reviewer review, operator mutation; lookup separate purpose/quote |
| Outreach | Existing queue/editor/review, mobile stack; human names; technical IDs in details | No draft, choose authorized context | Bounded context/list/job reads | Unified dirty Save/Discard/Cancel; stale/revoked policy blocks export | Exact-context reviewer approval; sender separate; delivery403 |
| Results | Buyer list first; usage and manual-event panels disclosed separately | Zero denominator em dash; no manual events | Scoped UTC usage/history reads | Unavailable cannot look like zero; history retry; append correction reason | Viewer no writes; manual source explicit |
| Settings/Operations | Name-based member directory; scoped job list; technical IDs/details; role-specific panels | No jobs/member matches | Real20-row pages; concise live status |503/read retry; same scope/status on refresh; old-generation replies discarded | Admin directory/readiness/audit; own jobs for non-admin |

## Interaction requirements

- en and zh-HK at1280 and390; actual native Chromium200% zoom via the isolated test extension tabs.setZoom(2), with1440 rendered as720 CSS pixels and devicePixelRatio2; no page-level horizontal overflow. Native zoom automated evidence is separate from actual screen-reader/staff observation.
- All actionable controls have accessible names, visible focus, keyboard path; drawer Escape returns trigger focus; dirty-dialog focus remains deliberate. Do not wrap whole changing jobs/research detail in role=status/aria-live. Announce status/stage transitions only; technical counters available visually in details.
- Keep canonical IDs in details/URLs and debug lookup, not the primary human identity label. Preserve full canonical user IDs alongside names in eligible-owner dropdown choices: duplicate names and UUID suffixes must remain distinguishable before a human chooses; the selected-owner summary stays name-based. Do not use email to infer/link/promote identities.
- UTC period is half-open; language change does not alter dates. Fixed-point money rendered as recorded; no float recomputation. Outcomes clearly manual, append-only correction and no email/sent inference.
- Scope/token generation changes never allow old replies or writes to replace current state. One domain API and unchanged authorization remain mandatory.

## Evidence and external gates

New audit-daily-ux.spec.ts must be actually matched/executed by audit config. Strict disposable loopback/Docker DB suites BUYEROS_STRICT_INTEGRATION=1 and zero skips. Historical demo responsive cases can be separately executed using their actual matching config and must be labelled demo.

U12 protocol:3-5 consenting staff each execute five tasks with authorized resettable fixture dataset, capture task start/end, assistance, wrong-scope attempts/commits, completion and mistakes before/after. Denominator15-25; target>=90% completion and zero wrong-scope writes. No employees available in this session: baseline duration/completion/error fields NULL (not0); gate blocked. Fixture automation duration is only machine test runtime.

U11 protocol: actual assistive technology/browser/operator recorded; keyboard and DOM semantics are not a screen-reader result. No screen-reader operator available: human gate blocked.

Per-module UI rollback must retain immutable data, API/RLS/approval/dirty and economic safety guards. No DB migration planned; auth/Cloudflare cutover separate. Author review cannot claim independent approval or eight-module live acceptance.
