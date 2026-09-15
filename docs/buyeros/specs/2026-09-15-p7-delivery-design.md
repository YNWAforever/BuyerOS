# P7 design — controlled delivery (design only, not activated)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers task **BO-030** (phase P7). Approval acknowledged with "ok"; this is a design input and **not** approval to implement, connect a mailbox, or send anything.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, contact purchase, mailbox connection, message, send, commit or push is authorized or performed by this document. MVP-A contains no delivery capability.

Related records: [P1](2026-09-15-p1-boundary-design.md), [P2](2026-09-15-p2-persistence-foundation-design.md), [P3](2026-09-15-p3-discovery-fit-design.md), [P4](2026-09-15-p4-contact-guardrails-design.md), [P5](2026-09-15-p5-draft-approval-export-design.md), [P6](2026-09-15-p6-hardening-pilot-design.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [05 test/security/release](../05_TEST_SECURITY_AND_RELEASE.md).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).

## Scope

Define a future, separately approved controlled-delivery phase: one sender of record, verified terms and interfaces, jurisdiction/policy gates, suppression/reply/bounce loops, and an independent activation approval. **Nothing in this document is implemented or activated.**

In scope: BO-030 (design and task-pack definition only). Out of scope: any sending implementation, mailbox connection, or activation; and all MVP-A capabilities.

## Disabled delivery boundary (MVP-A)

- Delivery remains a constant-disabled capability. The documented `disabledDeliveryBoundary` operation returns `403 DELIVERY_DISABLED` regardless of an approval.
- A draft has **no `Sent` state**. Copy/download/export create only audit/export events. Manual outcomes preserve `source=manual` and never imply a synchronized reply or measured causality.
- No graph edge, worker task, credential, endpoint, or mailbox adapter for delivery exists in MVP-A. Approving a draft does not enable sending.

## Channel and sender of record

- **Channel (default):** a single **transactional ESP API** as the sender of record. No SMTP/IMAP mailbox in MVP-A. (This question was left unanswered in session; the ESP default is recorded and open to owner change.)
- `projects.active_sender_identity_version` points to an immutable `sender_identity_versions` record (display name, role, organization, business email, version key, reviewer/time, retired state).
- Before any activation, **domain ownership and SPF/DKIM/DMARC** alignment, provider terms, and sending-domain reputation must be verified. Configuration review does not prove mailbox/domain ownership.

## Preconditions for any future send

- A valid **exact-context approval** (draft id/revision/content hash, recipient value hash + version, evidence set hash, policy decision IDs/versions, sender version, suppression epoch) bound to the current context.
- Current **suppression** check, honored **opt-out**, and rate/volume limits.
- Completed jurisdiction/policy and **legal review** for the applicable markets and entities (B-POLICY / B-DELIVERY).
- Explicit, separate **activation authorization** naming environment, users, market/purpose, provider, spend cap, and time window.

## Lifecycle loops to design

- **Bounce and complaint** handling mapped back to the recipient/contact and the originating approval; repeated failure pauses the channel.
- **Reply ingestion** recorded as a distinct delivery-phase event, never confused with manual outcomes.
- **One-click opt-out/unsubscribe** feeding `suppressions` with a versioned **suppression epoch**; suppression removal never restores a prior approval.
- **Delivery status** is a separate dimension from approval and from contact validity.

## Idempotency, kill switch and audit

- One **send key per approval**; the same approval is never sent twice; an **uncertain provider acceptance reconciles** rather than retrying blindly (same unknown-hold discipline as P4).
- A **kill switch** stops new sends immediately, reconciles in-flight operations, and requires explicit approval to resume — never an automatic resume.
- Immutable **send events** reference the exact approval and store minimal personal payload; copy/export never becomes `sent`.

## Separation and governance

- BO-030 is a separate P7 task pack with its **own activation approval**. BO-028/BO-029 completion never auto-unlocks delivery.
- Any provider evaluation at that time must verify the exact interface, cost bound, idempotency/status semantics, and data-use rights before activation. No invented provider API, endpoint, or model identifier.

## Interfaces

Future delivery endpoints are **not** defined in the current proposed OpenAPI and must not be invented. The only present contract is the disabled boundary that always rejects. A future pack must add reviewed operations and schemas.

## Testing (PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-030-01 | MVP-A direct attempts to send/schedule/import a mailbox all fail; no active sender/credentials/endpoint exists; approval never becomes `sent`; activation requires separate authorization |

## Assumptions, blockers and non-goals

- **Blocked by:** B-DELIVERY, B-APPROVAL, B-POLICY (legal/jurisdiction), and provider terms.
- **Non-goals:** implementing or activating any sender, connecting a mailbox, sending a message, provider selection, provisioning, migrations, and any Build action.

## Completion criteria

No task is completed by this document. BO-030 may be marked DONE only when its design-review acceptance evidence and separate approval obligations exist. Delivery stays disabled until an independently approved activation.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. Any future activation must be independently revocable via the kill switch without discarding financial or audit records.
