# Native PowerPoint Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. The user adopted the written spec and explicitly chose direct implementation; execute inline without another plan approval pause.

**Goal:** Upload, recover, preserve and read original private PowerPoint attachments in the existing BuyerOS product workflow.

**Architecture:** Add bounded upload sessions/chunks and immutable slide text to the existing PostgreSQL attachment lifecycle. A credential-free resource-capped parser reads OOXML; the client retains operation metadata and reconciles unknown results before resuming. Final bytes, document, provenance and receipt commit atomically.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/Alembic, Python zipfile/defusedxml, React/TypeScript, pytest and built Playwright fixtures.

**Spec:** `docs/superpowers/specs/2026-10-14-native-pptx-attachments-design.md`

## Global Constraints

- PPTX 20 MiB, legacy types 5 MiB, chunks 2 MiB, maximum ten chunks; no public original-file URLs or credentials in parser/URLs.
- Parser: eight-second wall deadline, Linux 512 MiB / six CPU seconds, 1,000 entries, 64 MiB expanded, 100 slides, 2 MiB/XML, 100,000 UTF-8 text bytes, 256 KiB output.
- Preserve workspace/actor scope, immutable content/digests, complete save/unknown-write semantics and all original tests. No paid research, drafts, mail, identity linking or role/budget changes.
- One-hour active staging access, two active sessions/actor and eight/workspace. Ordinary bounded cleanup; no unrequested scheduler.
- Exact full CI before production release. Customer files and evidence stay outside Git. Existing source, historical failures and untracked artifacts stay intact.

## Review Focus

- Nonstandard presentation order must retain actual page provenance (Task 1).
- Concurrent completion/archiving or revoked membership must never expose an unauthorized document (Task 3).
- A second browser tab/new idempotency key must not duplicate the same valid file (Tasks 3–4).
- Multipart/base64 overhead must remain below the hosting body cap (Tasks 3–4).
- A download interrupted by scope change or digest corruption must produce no file (Tasks 3–4).

### Task 1: Bounded OOXML parser

**Files:** create `services/api/buyeros_api/execution/pptx_parser.py`, `pptx_parser_child.py`, `services/api/tests/test_pptx_parser.py`; modify API/worker lockfiles and API dependency declaration.
**Interfaces:** `parse_pptx(body: bytes) -> dict` returns `slides` (`number,text,classification`), bounded `metadata`, and labeled `facts` with page-prefixed excerpts. `PptxParserTimeout` distinguishes deadline exhaustion.
- [ ] Write real ZIP/relationship fixtures. Assert reversed manifest order yields literal `Slide 1`/`Slide 2` text and image-only yields zero text/facts; external/embedded content is not loaded.
- [ ] Run `uv run --frozen pytest tests/test_pptx_parser.py -q` (expected RED, missing parser).
- [ ] Implement parent/child, hardened XML, whole-package caps, CPU/memory/deadline, actual slide order and literal extraction; add dependency and frozen locks.
- [ ] Run new parser + existing ingestion/PDF/subprocess tests (expected GREEN, zero skips); verify supplied files privately without copying them into repo.
- [ ] Commit parser task and ledger tests/results.

### Task 2: Tenant-safe staging schema

**Files:** create `db/document_uploads.py`, migration `0053_resumable_documents.py`, `tests/test_document_upload_schema_db.py`; modify `db/ingestion.py`, `db/__init__.py`, `object_store.py`.
**Interfaces:** `DocumentUpload`, `DocumentUploadChunk`, `DocumentSlide`; `OfferDocument.extraction_metadata`; private store max 20 MiB with bounded slice reads. Session manifest fixes type, filename, length, SHA-256 and chunk geometry.
- [ ] Add real PostgreSQL tests asserting cross-tenant FK/RLS rejection, immutable hash-checked chunks, original-object bounds and populated downgrade refusal.
- [ ] Run targeted schema tests (expected RED: missing table/schema).
- [ ] Add additive migration/FORCE RLS/indexes/immutable triggers/receipt-head guards and models. Preserve old metadata/bytes and runtime controls.
- [ ] Run targeted migration/RLS/object-store tests with disposable DB (expected GREEN, zero skips).
- [ ] Commit schema task and ledger results.

### Task 3: Upload lifecycle and source reads

**Files:** create `services/document_upload_service.py`, `api/routes/document_uploads.py`, `tests/test_document_upload_routes_db.py`; modify router registration, schemas/contracts, common document projection and deletion/expiry cleanup.
**Interfaces:** start/status/put-chunk/complete routes from spec; GET slide page and bounded original-content chunks. Completion uses Task 1 result and Task 2 models and returns an existing OfferDocument envelope/receipt.
- [ ] Add real API/DB cases for missing segment, conflicting digest, replay, same-file dedup, quotas, expiry, authority change/archive race, rollback, lost response recovery, original slices, deleted/expired reads and false page provenance.
- [ ] Execute route tests against old router (expected RED: unsupported routes).
- [ ] Implement authorization at every boundary, fixed manifest geometry, immutable writes, same-actor reconciliation, short transactions with parsing outside, project/session locks and atomic final bytes/document/slides/outbox/receipt.
- [ ] Add actor/workspace active limits and bounded cleanup; authoritative source/page lookup uses current document read permission and never returns private keys.
- [ ] Run targeted routes + old attachment/save/authorization tests (expected GREEN, zero skips), then update generated contracts through existing scripts.
- [ ] Commit lifecycle task and ledger results.

### Task 4: Resumable client and attachment UI

**Files:** create `services/live/document-upload.ts`, `tests/document-upload-checks.mjs`; modify `features/live/offer-documents.tsx`, localized copy, document transport fixtures and type contracts.
**Interfaces:** workflow upload/reconcile/original download/slide page APIs consumed by existing attachment panel; callbacks preserve existing fact/save structures. Store only actor/workspace/project-bound operation metadata, not bytes/tokens.
- [ ] Write actual-client boundary tests asserting retained upload ID after lost start/complete response, same-file reselection, foreign scope cancellation, duplicate prevention and rejected corrupt original download.
- [ ] Run tests before implementation (expected RED: no resumable client).
- [ ] Implement hash and fixed-size segments, readback before retry, finite progress/recovery, image-only message, slide provenance and verified original download. Legacy files above 4 MiB use chunks; smaller legacy files preserve old upload.
- [ ] Run affected frontend/auth/transport tests, TypeScript and lint (expected GREEN); ensure no partial file or stale result after scope switch.
- [ ] Commit client/UI task and ledger results.

### Task 5: Built workflow regression and complete CI

**Files:** add built-browser native attachment journey and fixture ZIP generator; update only strict discovery counts/new JUnit gate files and relevant native schema-head assumptions.
- [ ] Capture built-browser RED against the previous workflow for native upload/recovery/download/source/save.
- [ ] Complete real built fixture verification: no paid jobs, source hash, lost response/reload, complete profile persistence, image-only display and scope/permissions.
- [ ] Run complete API/worker/frontend/build checks; discovery must equal JUnit with zero required skips. Retain all prior 133 browser cases and all historical logs.
- [ ] Commit final integration; fresh whole-branch review and focused RED→GREEN for any actionable finding. Push exact task branch/PR and require all final-head CI jobs success.

### Task 6: Production release and original-file acceptance

**Files:** private release/export/backup/migration/readback reports under `work`, never committed.
- [ ] Rehearse additive migration, downgrade guard and previous-source reads on disposable DB and isolated Neon branch; prepare exact source export and backup/atomic migration pack.
- [ ] After exact final CI success, verify source/project/runtime region; build candidate with same Singapore placement and paid controls unchanged.
- [ ] Apply authorized additive production migration with preconditions/backup; check schema/RLS/old business data. Probe candidate then promote exact deployment.
- [ ] Upload two supplied PPTX originals through UI; reconcile any unknown action, verify original hashes/slide counts/page text/image-only state and download, save/reopen new profile source links and preserve old versions/24 buyers.
- [ ] Read-only final database acceptance: original private bytes/digests, receipts/provenance, zero research/drafts/spend/holds and disabled runtime. Record screenshot/CI/SHA/deployment evidence and update PR.
