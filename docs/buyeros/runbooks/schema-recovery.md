# C61-31 / C61-32 schema recovery

October 11 source baseline is `cbbe0e93b0132ae07ff0d87f6cc57f871f13200e`.
F23 is the request-correlated 42P01 incident. F21 remains a separate historical
unknown. This procedure does not authorize a production change.

The named BuyerOS production branch owner read observed 0033, one canonical
user and one active membership. An independent connection as `buyeros_api`
confirmed the absent identity relation and directory function, public schema
usage, and nonprivileged role. The sensitive Vercel database environment record
has the same ID/update time as its retained initialization, but its value is
unreadable. **That is insufficient to prove the actual deployment connection.**
Decision D remains open; A is supported for the named branch only.

| Artifact / flow | Necessary expansion | Acceptance still required |
|---|---|---|
| Workspace directory / Auth0 exact resolver | 0033 rate limiter; 0038 restricted directory; 0039 complete canonical backfill/triggers/column grants | Same deployment target, exact principal mapping, current roles/project, retry/reload and negative canaries |
| Current full API source | Reviewed chain through 0050, including contact retention and delivery ledger | Route-specific schema/grants and source/config receipt |
| Current worker | Reviewed chain through 0050 and actual selector/epoch/backend | Runtime-role grants, committed heartbeat, fencing; backend currently unknown |
| Read-only operator probe | SELECT(version_num) on Alembic metadata, in addition to application grants | Production role currently lacks it; no grant has been applied |
| Compatible Neon rollback | Existing pinned compatible API and corresponding frontend | Real artifact IDs and real Neon-only session; fixture alone is insufficient |

The isolated 0033 rehearsal observes 42P01 before the explicit existing
0034–0050 expansion, then resolves the same canonical UUID. Historical user,
membership, preference rows and FK definitions remain unchanged; new policies
are additive; runtime role stays non-superuser/NOBYPASSRLS. Revocation survives
re-running the exact target. Existing strict cutover cases independently cover
unknown holds, tombstones and the compatible cold API rollback. These are owned
PG16 evidence, not proof for the named PG18 production branch.

Before selecting A/B/C, obtain a same-deployment connection/config provenance
receipt. Confirm source/tree, endpoint fingerprint, database, branch metadata,
runtime login, search_path, relations, required function signature/EXECUTE,
column SELECT, FORCE RLS and exact canonical account mapping. An owner catalog
read only distinguishes absence from runtime visibility; it cannot replace the
actual runtime login. The probe accepts a secret environment DSN, never argv:

```text
uv run --frozen python tools/check_schema_readiness.py --contract PRIVATE_CONTRACT.json --output NEW_READBACK.json
```

Set `BUYEROS_SCHEMA_CHECK_DATABASE_URL` only in that operator child process.
The contract's independently verified target receipt must be bound to the
deployment. Unknown target/head is blocked. Do not place this secret in a test
fixture. Positive owned probes use only an explicit test-clone metadata column
grant; production has not received that privilege.

The review packet lists the exact 17 revisions/file hashes and offline SQL hash
in `docs/buyeros/release/schema-change-set.json`. Freeze a fresh restore point,
the from/to heads, row/FK/identity/revocation/hold readback hashes, verified
compatible frontend/API artifact IDs, lock budget, observation owner and
window before asking for the bounded change authorization. The old 0033
initialization authorization was consumed and does not authorize this packet.

For A, use only the reviewed explicit additive target and backfill/grants. For
B, correct the confirmed connection target without copying/recreating users.
For C, repair only demonstrated visibility/grant differences. D continues
diagnosis. No branch runs automatically on request/build/startup; no stamp,
empty identity table, email link, role widening or RLS disable is permitted.

Rollback stops new admissions/link writes, fences the actual worker epoch and
retains additive identities, revocations, historical rows and unknown holds.
Use only verified compatible frontend and API artifacts. Never drop identities
or perform schema downgrade to make an Auth0-only artifact usable. Stop on any
wrong target, UUID/FK/hold change, authorization leak or lock-budget breach.

G0 needs real known-account workspace 200 with the correct current roles and
project, true empty membership, foreign tenant/revoked denial and retry/reload
readback at the same source/config/schema tuple. Paid providers and worker
activation are independent. `/health/live`, READY and fixture CI do not close G0.
