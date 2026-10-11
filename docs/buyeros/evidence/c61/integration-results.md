# C61-02 selective Q integration and verification

Tested integration source: `d90431dd4a5a448b54fcb29b4920f6d07982e4d9`. Evidence dates below are actual UTC run dates, independent of the supplied audit date.

Status: source integrated; focused fixtures verified; complete built-browser acceptance remains blocked by the local Docker/disk environment. No deployment or live acceptance.

| Group | Adopted source commits | New commit | Observed focused result | Artifact |
|---|---|---|---|---|
| Q01 | 8251027 | f37527613ca473ed794a0c2a0f99a02aa88d6e12 | 1 cases / 0 fail / 0 skip | artifacts/c61/Q01.log |
| Q03 | f5936ce | 650f25b5ca2ab1b8d96098d098629275b7b7eb7d | typecheck exit 0; no behavioral case count (not acceptance) | artifacts/c61/Q03.log |
| Q04 | fc8fae7 | a16990509e099a17ce26948c6a02cdca8e0ea2c8 | 3 cases / 0 fail / 0 skip | artifacts/c61/Q04.log |
| Q15 | 3efd1f3 | aa957aa683a37e7fcd0041392d87ba8580c38a62 | 7 cases / 0 fail / 0 skip | artifacts/c61/Q15.log |
| Q02 | fb18481 | c61ad8f5387af1c645e78eef546aef254a8eefea | 7 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q02.log |
| Q05 | 4cd0f48 | 3abd73aeb2d4000619ac80ee0a0b53de43c73034 | 13 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q05.log |
| Q06 | b3477e3 | dda5cfc8e0cbd5ca8975baabbea6800381bc8dee | 11 cases / 0 fail / 0 skip | artifacts/c61/Q06.log |
| Q07 | a2696e1 | 16570ca3fdf09602a1c63514f7847785c4110011 | 18 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q07.log |
| Q12-api | 63d140b | 14784296f4f174c605aea6d279d0ccc5fdc96ae4 | 31 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q12-api.log |
| Q12-ui | 70d2e54 | 9615bd1b1afb29e19087173f9498d1a1bb699e95 | 2 cases / 0 fail / 0 skip | artifacts/c61/Q12-ui.log |
| Q08 | c98fb68 | 0ecd85021ba2c345507d9f5c36c900ec6b490c7e | 19 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q08.log |
| Q14 | 1aab3dd | ecb2f2ccc742571dd7e260a8f373572513b5e0a1 | 3 cases / 0 fail / 0 error / 0 skip | artifacts/c61/Q14.log |
| Q09-support | 85686a6, 3843623, 35e8591, 6e7335b, 1953d61, f70501a | 0f10c967a90b4fafa11536a5d07d0786ef856877 | 4 cases / 0 fail / 0 skip | artifacts/c61/Q09-support.log |
| access-revocation | 540696b, 25694d3 | b250c269d50daa428f36487d18f48027a7723d64 | 4 cases / 0 fail / 0 skip | artifacts/c61/access-revocation.log |
| fixture-cleanup | d7ab5b6 | 5765b8787218d64793c8934efacec4bf7ceaf5d3 | 24 cases / 0 fail / 0 skip | artifacts/c61/fixture-cleanup.attempt2.log |
| CI-contract-preferences | 546a037 | 35226658ebc15367fd643b207184464e6108d6f6 | 8 cases / 0 fail / 0 error / 0 skip | artifacts/c61/CI-contract-preferences.log |

## Required suite layers

- Fresh source d90431d: 45 audit Node cases passed, zero fail/skip/cancel; TypeScript exit 0; Playwright discovers 96 cases in 14 files. Discovery alone is not execution.
- Required PostgreSQL16 DB suite on 35226658: 64 cases, zero fail/error/skip, real non-owner runtime roles. Source-bridge JSON proves the API, frontend product, live services and public contracts subtrees are unchanged through d90431d; fixture/CI changes are listed separately.
- Built fixture regression on 9edb6cf: 92/96 passed, four failures, zero skip. All four were traced to owned fixture isolation/response observation and preserved before correction.
- Correction validation: 23 cases passed, zero fail/error/skip; exact tested staged tree is recorded, and the four changes became d90431d. Roles/locale/rate-window resets apply only to owned synthetic actors. Research counts assert new effects relative to the observed baseline and retain all accepted history.
- Full d90431d rerun aborted with ENOSPC after 25 observed pass lines. It produced no fresh complete JUnit: the old 23-case report is explicitly rejected by the ENOSPC record. A subsequent run created a fresh zero-case report because Docker fixture startup timed out; zero cases failed the gate.
- Local host space was recovered by deleting only this run's partial installation and package-download caches. Installed packages, source, audit inputs and prior failed artifacts were preserved. Docker Desktop processes remain but its engine pipe became unavailable; restarting the shared service requires the pending specific user authorization.
- The transient verification wrapper now requires a fresh JUnit report; complete local built suite and remote CI remain pending. It never counts an old report, an empty suite or fixture success as live acceptance.

The original Windows dev-mode hydration overlay failure and earlier 81-pass/3-fail/12-not-run built fixture run remain historical run artifacts. The supported owned built runner and CI now check positive discovery and required zero fail/error/skip reports. No failed assertion was removed.

## Scope and release gates

84 public operations and additive 0037_bulk_manifests are retained. Original audit fields and 114 results remain byte-preserved; only execution fields in copies are updated. No Neon spike or Q13 RLS policy was merged.
Fixture/built preview, real provider, production API/schema/worker/selector/epoch readback and human UAT are separate. Release A (research plus approved export), Neon-only and native send are all not accepted. Production research503 and send403 remain valid protected boundaries.

## Rollback

Revert by the independent Q commit groups above, retaining immutable revisions, approvals, manifests, audit and accepted/unknown operations/holds. Do not destructively downgrade ledger/schema or replay successful bulk rows. CI/fixture corrections can be reverted separately. Nothing has been deployed.
