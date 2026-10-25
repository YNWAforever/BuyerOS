# BuyerOS Core Isolated Acceptance Plan

> **For agentic workers:** Execute the bounded, already authorized acceptance in this existing task. Use test-driven local fixes and preserve all earlier onboarding evidence.

**Goal:** Create a requirement, execute deterministic fixture research, inspect persisted results, and save an unsent outreach draft, including reload, retry, recovery and workspace isolation.

**Architecture:** Retain the existing Vinext/FastAPI/PostgreSQL architecture. Reuse the synthetic OIDC browser helpers and deterministic test-only Celery provider; stop the journey at draft persistence. Use the existing owned-container identity gate before SQL clients.

**Tech Stack:** Node 24, pnpm 11.25.0, Python 3.12, Playwright/system Chromium, PostgreSQL 16, disposable Valkey/Celery.

**Spec:** The user's approved bounded phase in this existing task: synthetic data/providers only; no push, merge, deployment, production data/Auth/secrets, paid models or outreach sending.

## Global Constraints

- Baseline: branch `work`, HEAD `3c79793bea0c0defdf62cec28fa8ef9d3d8ffda2`, initially clean; no new worktree/task.
- Existing source, evidence and lockfiles must be preserved except minimal necessary local product fixes.
- Before SQL: independently match container ID, image ID, ownership label, local daemon, no bind mounts, exact loopback port/database and synthetic issuer; save receipts.
- Fixture seeding and controlled policy data exist only inside this run's verified disposable container. No environment/network/security setting changes.
- No delivery endpoint calls, approval/export detours, or external provider requests.

## Review Focus

- A committed response lost in transport must retry the same immutable command/key rather than create another revision or a false conflict.
- Changed content, draft, actor or workspace must not reuse an earlier command identity.
- Reload must recover persisted requirement/results/draft, not merely a success notification.
- Real existing foreign run/draft resources must stay inaccessible and unchanged.
- Cleanup must identify only this run's allocated fixtures; earlier reports remain available.

### Task 1: Bound the existing browser harness

- [x] Add a dedicated Playwright configuration and core-flow spec using existing synthetic helpers.
- [x] Establish and record the exact owned DB target before API/worker writes; use unique evidence/output locations.
- [x] Exercise profile creation/approval, durable research admission, deterministic worker results, and draft save/reload without delivery.

### Task 2: Reproduce and minimally fix recovery failures

- [x] Add a browser case dropping the real committed draft-save acknowledgement; expect identical retry command/key and one persisted revision.
- [x] Run it against the baseline before any product fix; diagnose the actual failure.
- [x] Apply only necessary fixes using existing action-intent patterns; rerun the failing case and bounded journey.

### Task 3: Verify authorization and regressions

- [x] Add actual foreign-resource API regressions in `services/api/tests/test_core_flow_scope_db.py`.
- [x] Run relevant API/worker/unit/browser coverage, typecheck, lint and build; record exact commands/counts/diff fingerprint.
- [x] Obtain a read-only review of the final diff; resolve material findings with regression evidence.
- [x] Deliver evidence, unresolved defects and the exact real-integration approval scope. Leave source changes reviewable locally.
