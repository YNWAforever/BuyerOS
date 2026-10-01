# BuyerOS review inventory

This local T00–T30 release-candidate inventory records the pre-commit diff relative to base `f43a9d88b334c2c4029fa06fa71624ed52efe4a2`. `M` means tracked modification at that snapshot; `??` means newly created file at that snapshot. This is a historical inventory. Generated fixture evidence and subsequent deployment proof are distinguished in `../RELEASE_READINESS.md`; current source/checkpoint details appear in `../REMAINING_DEVELOPMENT_STATUS.md`.

Exact working-tree paths: **410**.

```text
 M .gitignore
 M README.md
 M app/globals.css
 M app/layout.tsx
 M docs/buyeros/PROGRESS.md
 M docs/buyeros/contracts/openapi.proposed.yaml
 M docs/buyeros/tasks/index.json
 M features/buyers/detail.tsx
 M features/live/buyer-detail.tsx
 M features/live/buyers.tsx
 M features/live/offer-wizard.tsx
 M features/live/overview.tsx
 M features/live/profile.tsx
 M features/providers/workspace-session.tsx
 M features/workspace.tsx
 M locales/index.ts
 M package.json
 M pnpm-lock.yaml
 M services/api/buyeros_api/api/app.py
 M services/api/buyeros_api/api/auth.py
 M services/api/buyeros_api/api/deps.py
 M services/api/buyeros_api/api/errors.py
 M services/api/buyeros_api/api/idempotency.py
 M services/api/buyeros_api/api/jwks.py
 M services/api/buyeros_api/api/routes/buyers.py
 M services/api/buyeros_api/api/routes/health.py
 M services/api/buyeros_api/api/routes/icp.py
 M services/api/buyeros_api/api/routes/projects.py
 M services/api/buyeros_api/api/routes/reviews.py
 M services/api/buyeros_api/api/routes/workspaces.py
 M services/api/buyeros_api/api/schemas.py
 M services/api/buyeros_api/api/unimplemented.py
 M services/api/buyeros_api/api/verifier.py
 M services/api/buyeros_api/db/__init__.py
 M services/api/buyeros_api/db/budget.py
 M services/api/buyeros_api/db/buyers.py
 M services/api/buyeros_api/db/contact.py
 M services/api/buyeros_api/db/drafts.py
 M services/api/buyeros_api/db/icp.py
 M services/api/buyeros_api/db/models.py
 M services/api/buyeros_api/db/outbox.py
 M services/api/buyeros_api/db/outcomes.py
 M services/api/buyeros_api/db/policy.py
 M services/api/buyeros_api/db/runs.py
 M services/api/buyeros_api/db/worker.py
 M services/api/buyeros_api/providers/search.py
 M services/api/buyeros_api/services/approval_fingerprint.py
 M services/api/buyeros_api/services/approval_service.py
 M services/api/buyeros_api/services/budget_service.py
 M services/api/buyeros_api/services/buyer_read.py
 M services/api/buyeros_api/services/buyer_review.py
 M services/api/buyeros_api/services/buyer_selection.py
 M services/api/buyeros_api/services/buyer_view.py
 M services/api/buyeros_api/services/callback.py
 M services/api/buyeros_api/services/canonicalize.py
 M services/api/buyeros_api/services/confirm_service.py
 M services/api/buyeros_api/services/csv_export.py
 M services/api/buyeros_api/services/draft_service.py
 M services/api/buyeros_api/services/fit.py
 M services/api/buyeros_api/services/icp_service.py
 M services/api/buyeros_api/services/policy_service.py
 M services/api/buyeros_api/services/provider_op.py
 M services/api/buyeros_api/services/query_plan.py
 M services/api/buyeros_api/services/quote_service.py
 M services/api/buyeros_api/services/run_events.py
 M services/api/buyeros_api/services/safe_fetch.py
 M services/api/buyeros_api/services/settlement.py
 M services/api/buyeros_api/services/usage.py
 M services/api/buyeros_api/settings.py
 M services/api/pyproject.toml
 M services/api/tests/conftest.py
 M services/api/tests/test_api_app.py
 M services/api/tests/test_api_buyers.py
 M services/api/tests/test_api_health.py
 M services/api/tests/test_api_projects_db.py
 M services/api/tests/test_api_routes_contract.py
 M services/api/tests/test_approval_fingerprint.py
 M services/api/tests/test_buyer_review_db.py
 M services/api/tests/test_callback.py
 M services/api/tests/test_canonicalize.py
 M services/api/tests/test_csv_export.py
 M services/api/tests/test_fit.py
 M services/api/tests/test_icp.py
 M services/api/tests/test_policy.py
 M services/api/tests/test_provider_op.py
 M services/api/tests/test_search_adapter.py
 M services/api/uv.lock
 M services/generated/approval-golden-vectors.json
 M services/generated/buyeros-api.ts
 M services/live/client.ts
 M services/live/mapping.ts
 M services/live/profile.ts
 M services/live/session.ts
 M services/live/writes.ts
 M services/worker/buyeros_worker/app.py
 M services/worker/buyeros_worker/cli.py
 M services/worker/buyeros_worker/config.py
 M services/worker/buyeros_worker/dispatcher.py
 M services/worker/buyeros_worker/engine.py
 M services/worker/buyeros_worker/handlers/__init__.py
 M services/worker/buyeros_worker/handlers/capability_blocked.py
 M services/worker/buyeros_worker/handlers/fetch_evidence.py
 M services/worker/buyeros_worker/run_emitter.py
 M services/worker/buyeros_worker/run_lifecycle.py
 M services/worker/buyeros_worker/tasks.py
 M services/worker/pyproject.toml
 M services/worker/tests/conftest.py
 M services/worker/tests/test_app.py
 M services/worker/tests/test_tasks.py
 M services/worker/tests/test_valkey_integration.py
 M services/worker/tests/test_worker_integrity_db.py
 M services/worker/uv.lock
 M tests/live-adapter-checks.mjs
 M vite.config.ts
?? .github/workflows/buyeros-ci.yml
?? app/auth/callback/page.tsx
?? artifacts/t29-benchmark-10k-100ws-asgi.json
?? artifacts/t29-benchmark-10k-100ws-combined-dispatcher.json
?? artifacts/t29-benchmark-10k-100ws-combined.json
?? artifacts/t29-benchmark-10k-100ws-distinct-corrected-dispatcher.json
?? artifacts/t29-benchmark-10k-100ws-distinct-corrected.json
?? artifacts/t29-benchmark-10k-100ws-distinct-dispatcher.json
?? artifacts/t29-benchmark-10k-100ws-distinct.json
?? artifacts/t29-benchmark-10k-100ws-post-rate-pool-dispatcher.json
?? artifacts/t29-benchmark-10k-100ws-post-rate-pool.json
?? artifacts/t29-benchmark-1k-1ws-asgi.json
?? artifacts/t29-benchmark-1k-1ws.json
?? artifacts/t29-dispatch-100ws.json
?? artifacts/t29-mutations-20x20-clean.json
?? artifacts/t29-mutations-20x20-post-rate-pool.json
?? artifacts/t29-mutations-20x20.json
?? artifacts/t29-screenshots/en-1440-post-retry.png
?? artifacts/t29-screenshots/en-1440.png
?? artifacts/t29-screenshots/en-390-post-retry.png
?? artifacts/t29-screenshots/en-390.png
?? artifacts/t29-screenshots/en-buyer-list-390-post-extraction.png
?? artifacts/t29-screenshots/en-buyer-page-2-1280-post-extraction.png
?? artifacts/t29-screenshots/zh-HK-1440-post-retry.png
?? artifacts/t29-screenshots/zh-HK-1440.png
?? artifacts/t29-screenshots/zh-HK-390-post-retry.png
?? artifacts/t29-screenshots/zh-HK-390.png
?? artifacts/t29-screenshots/zh-buyer-full-390-post-extraction.png
?? artifacts/t29-screenshots/zh-results-usage-390-post-extraction.png
?? artifacts/t29-workspace-lint-after1.json
?? artifacts/t29-workspace-lint-after2.json
?? artifacts/t29-workspace-lint.json
?? artifacts/t30-screenshots/en-fixture.png
?? artifacts/t30-screenshots/ui-worker-grounded-en-fixture.png
?? artifacts/t30-screenshots/ui-worker-grounded-zh-mobile-fixture.png
?? artifacts/t30-screenshots/zh-mobile-fixture.png
?? docs/buyeros/PILOT_EXECUTION_RECORD.md
?? docs/buyeros/RELEASE_READINESS.md
?? docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
?? docs/buyeros/decisions/2026-09-27-contract-delta.md
?? docs/buyeros/performance-baseline.md
?? docs/buyeros/pilot/evaluation-protocol.md
?? docs/buyeros/provider-capabilities.md
?? docs/buyeros/remaining/API_OPERATION_STATUS.csv
?? docs/buyeros/remaining/CHANGED_FILES.md
?? docs/buyeros/remaining/TASKS.json
?? docs/buyeros/runbooks/recovery.md
?? docs/buyeros/runbooks/release.md
?? docs/buyeros/runbooks/retention.md
?? docs/buyeros/runbooks/worker-runtime.md
?? features/live/budgets.tsx
?? features/live/bulk-actions.tsx
?? features/live/buyer-management-controls.tsx
?? features/live/buyer-results.tsx
?? features/live/contact-quote.tsx
?? features/live/drafts.tsx
?? features/live/export-dialog.tsx
?? features/live/locale.ts
?? features/live/navigation.tsx
?? features/live/offer-documents.tsx
?? features/live/operations.tsx
?? features/live/policy-settings.tsx
?? features/live/project-manager.tsx
?? features/live/results.tsx
?? features/live/run-progress.tsx
?? features/live/settings.tsx
?? features/live/workspace-picker.tsx
?? features/workspace/buyer-table.tsx
?? features/workspace/modals.tsx
?? features/workspace/navigation.tsx
?? features/workspace/route-view.tsx
?? features/workspace/shell.tsx
?? playwright.admin.config.ts
?? playwright.approval.config.ts
?? playwright.bulk.config.ts
?? playwright.buyer-management.config.ts
?? playwright.buyer.config.ts
?? playwright.config.ts
?? playwright.confirm.config.ts
?? playwright.contact-job.config.ts
?? playwright.cors.config.ts
?? playwright.draft.config.ts
?? playwright.exports.config.ts
?? playwright.ingestion.config.ts
?? playwright.live.config.ts
?? playwright.mvp-research.config.ts
?? playwright.mvp.config.ts
?? playwright.offer.config.ts
?? playwright.policy.config.ts
?? playwright.quote.config.ts
?? playwright.responsive.config.ts
?? playwright.run.config.ts
?? playwright.workbench.config.ts
?? playwright.zoom.config.ts
?? scripts/benchmark-buyer-mutations.py
?? scripts/benchmark-buyeros.py
?? scripts/check-required-tests.py
?? scripts/generate-api-types.mjs
?? scripts/generate-operation-routes.py
?? services/api/alembic/versions/0012_offer_basis_revision.py
?? services/api/alembic/versions/0013_project_link_constraints.py
?? services/api/alembic/versions/0014_buyer_management.py
?? services/api/alembic/versions/0015_policy_lifecycle.py
?? services/api/alembic/versions/0016_bulk_jobs.py
?? services/api/alembic/versions/0017_settings_audit.py
?? services/api/alembic/versions/0018_budget_ledger.py
?? services/api/alembic/versions/0019_offer_documents.py
?? services/api/alembic/versions/0020_research_provenance.py
?? services/api/alembic/versions/0021_run_bounds.py
?? services/api/alembic/versions/0022_research_checkpoints.py
?? services/api/alembic/versions/0023_contact_quote_basis.py
?? services/api/alembic/versions/0024_contact_job_execution.py
?? services/api/alembic/versions/0025_provider_callback_route.py
?? services/api/alembic/versions/0026_sender_identity_versions.py
?? services/api/alembic/versions/0027_draft_integrity.py
?? services/api/alembic/versions/0028_draft_approval_context.py
?? services/api/alembic/versions/0029_export_authorization.py
?? services/api/alembic/versions/0030_manual_outcome_provenance.py
?? services/api/alembic/versions/0031_retention_redaction.py
?? services/api/alembic/versions/0032_contact_retention.py
?? services/api/alembic/versions/0033_api_rate_windows.py
?? services/api/buyeros_api/api/routes/audit.py
?? services/api/buyeros_api/api/routes/budgets.py
?? services/api/buyeros_api/api/routes/buyer_management.py
?? services/api/buyeros_api/api/routes/documents.py
?? services/api/buyeros_api/api/routes/drafts.py
?? services/api/buyeros_api/api/routes/enrichment.py
?? services/api/buyeros_api/api/routes/exports.py
?? services/api/buyeros_api/api/routes/jobs.py
?? services/api/buyeros_api/api/routes/memberships.py
?? services/api/buyeros_api/api/routes/outcomes.py
?? services/api/buyeros_api/api/routes/policy.py
?? services/api/buyeros_api/api/routes/provider_callbacks.py
?? services/api/buyeros_api/api/routes/quotes.py
?? services/api/buyeros_api/api/routes/runs.py
?? services/api/buyeros_api/api/routes/settings.py
?? services/api/buyeros_api/api/routes/usage.py
?? services/api/buyeros_api/db/ingestion.py
?? services/api/buyeros_api/db/rate.py
?? services/api/buyeros_api/providers/base.py
?? services/api/buyeros_api/providers/contact.py
?? services/api/buyeros_api/providers/model.py
?? services/api/buyeros_api/services/api_rate_limit.py
?? services/api/buyeros_api/services/audit_service.py
?? services/api/buyeros_api/services/bulk_service.py
?? services/api/buyeros_api/services/buyer_management.py
?? services/api/buyeros_api/services/contact_result_service.py
?? services/api/buyeros_api/services/enrichment_service.py
?? services/api/buyeros_api/services/evidence_service.py
?? services/api/buyeros_api/services/export_service.py
?? services/api/buyeros_api/services/ingestion_service.py
?? services/api/buyeros_api/services/object_store.py
?? services/api/buyeros_api/services/offer_document_refs.py
?? services/api/buyeros_api/services/offer_source_policy.py
?? services/api/buyeros_api/services/outcome_service.py
?? services/api/buyeros_api/services/pinned_transport.py
?? services/api/buyeros_api/services/retention.py
?? services/api/buyeros_api/services/run_admission.py
?? services/api/buyeros_api/services/run_control.py
?? services/api/buyeros_api/services/run_usage.py
?? services/api/tests/benchmark_buyeros_case.py
?? services/api/tests/benchmark_mutation_case.py
?? services/api/tests/contract_validation.py
?? services/api/tests/icp_fixtures.py
?? services/api/tests/test_admin_operations_db.py
?? services/api/tests/test_auth_cache_lifecycle.py
?? services/api/tests/test_backup_restore_t28.py
?? services/api/tests/test_budget_atomicity_db.py
?? services/api/tests/test_budget_rollover_db.py
?? services/api/tests/test_bulk_jobs_db.py
?? services/api/tests/test_buyer_management_db.py
?? services/api/tests/test_contact_confirm_atomicity_db.py
?? services/api/tests/test_contact_job_migration.py
?? services/api/tests/test_contact_quote_migration.py
?? services/api/tests/test_contract_required_fields.py
?? services/api/tests/test_cors_http.py
?? services/api/tests/test_draft_approval_context_db.py
?? services/api/tests/test_draft_approval_migration.py
?? services/api/tests/test_draft_integrity_migration.py
?? services/api/tests/test_draft_persistence_db.py
?? services/api/tests/test_evidence_persistence_db.py
?? services/api/tests/test_export_migration.py
?? services/api/tests/test_exports_authorization_db.py
?? services/api/tests/test_fit_eval.py
?? services/api/tests/test_icp_validation_http.py
?? services/api/tests/test_icp_write_integrity_db.py
?? services/api/tests/test_idempotency_replay_db.py
?? services/api/tests/test_ingestion_migration.py
?? services/api/tests/test_ingestion_security.py
?? services/api/tests/test_lookup_quotes_db.py
?? services/api/tests/test_offer_document_routes_db.py
?? services/api/tests/test_outcome_migration.py
?? services/api/tests/test_policy_lifecycle_db.py
?? services/api/tests/test_profile_approval_races_db.py
?? services/api/tests/test_project_constraints_db.py
?? services/api/tests/test_provider_callbacks_db.py
?? services/api/tests/test_provider_contracts.py
?? services/api/tests/test_query_plan_bounds.py
?? services/api/tests/test_rate_pool_pressure_db.py
?? services/api/tests/test_required_test_gate.py
?? services/api/tests/test_research_checkpoint_migration.py
?? services/api/tests/test_research_migration.py
?? services/api/tests/test_retention_authorization_db.py
?? services/api/tests/test_run_admission_db.py
?? services/api/tests/test_run_admission_integration_db.py
?? services/api/tests/test_run_events_http.py
?? services/api/tests/test_run_migration.py
?? services/api/tests/test_sender_identity_db.py
?? services/api/tests/test_sender_identity_migration.py
?? services/api/tests/test_snapshot_access_db.py
?? services/api/tests/test_test_database_safety.py
?? services/api/tests/test_usage_outcomes_db.py
?? services/api/tests/test_workspace_listing_db.py
?? services/api/tools/serve_e2e_fixture.py
?? services/generated/operation-routes.ts
?? services/live/action-intent.ts
?? services/live/approval-fingerprint.ts
?? services/live/auth.ts
?? services/live/buyers.ts
?? services/live/download-text.ts
?? services/live/drafts.ts
?? services/live/exports.ts
?? services/live/operations.ts
?? services/live/outcomes.ts
?? services/live/quotes.ts
?? services/live/runs.ts
?? services/live/usage.ts
?? services/worker/buyeros_worker/checkpoints.py
?? services/worker/buyeros_worker/discovery_runner.py
?? services/worker/buyeros_worker/document_runner.py
?? services/worker/buyeros_worker/external_runner.py
?? services/worker/buyeros_worker/fetch_runner.py
?? services/worker/buyeros_worker/fit_execution.py
?? services/worker/buyeros_worker/fit_runner.py
?? services/worker/buyeros_worker/handlers/bulk_mutate.py
?? services/worker/buyeros_worker/handlers/contact_submit.py
?? services/worker/buyeros_worker/handlers/draft_generate.py
?? services/worker/buyeros_worker/handlers/reconcile.py
?? services/worker/buyeros_worker/handlers/retention.py
?? services/worker/buyeros_worker/metrics.py
?? services/worker/buyeros_worker/pdf_parser.py
?? services/worker/buyeros_worker/pdf_parser_child.py
?? services/worker/buyeros_worker/research_graph.py
?? services/worker/tests/benchmark_dispatcher_case.py
?? services/worker/tests/fixtures/__init__.py
?? services/worker/tests/fixtures/run_browser_research.py
?? services/worker/tests/fixtures/t30_celery.py
?? services/worker/tests/test_bulk_mutate_handler.py
?? services/worker/tests/test_contact_uncertainty_db.py
?? services/worker/tests/test_crash_recovery_matrix.py
?? services/worker/tests/test_discovery_limits.py
?? services/worker/tests/test_discovery_runner_db.py
?? services/worker/tests/test_dispatcher_runtime.py
?? services/worker/tests/test_external_runner_db.py
?? services/worker/tests/test_fetch_persistence.py
?? services/worker/tests/test_grounded_drafts.py
?? services/worker/tests/test_offer_document_worker_db.py
?? services/worker/tests/test_pdf_parser.py
?? services/worker/tests/test_research_fit_db.py
?? services/worker/tests/test_research_graph.py
?? services/worker/tests/test_research_restart_db.py
?? services/worker/tests/test_run_cancel_db.py
?? services/worker/tests/test_t30_broker_research.py
?? services/worker/tests/test_test_database_safety.py
?? services/worker/tests/test_worker_heartbeat.py
?? services/worker/tools/pump_e2e_bulk.py
?? tests/api-types-generation.test.mjs
?? tests/approval-fingerprint.test.mjs
?? tests/e2e-fixture-cleanup.test.mjs
?? tests/e2e/actual-browser-zoom.spec.ts
?? tests/e2e/admin-settings.spec.ts
?? tests/e2e/bulk-actions.spec.ts
?? tests/e2e/buyer-management.spec.ts
?? tests/e2e/buyer-results.spec.ts
?? tests/e2e/contact-confirm.spec.ts
?? tests/e2e/contact-job.spec.ts
?? tests/e2e/contact-quote.spec.ts
?? tests/e2e/daily-workbench.spec.ts
?? tests/e2e/draft-approval.spec.ts
?? tests/e2e/draft-editor.spec.ts
?? tests/e2e/exports.spec.ts
?? tests/e2e/harness.spec.ts
?? tests/e2e/live-auth-scope.spec.ts
?? tests/e2e/live-cors-errors.spec.ts
?? tests/e2e/mvp-a-journey.spec.ts
?? tests/e2e/mvp-a-research.spec.ts
?? tests/e2e/offer-ingestion.spec.ts
?? tests/e2e/offer-profile.spec.ts
?? tests/e2e/policy.spec.ts
?? tests/e2e/responsive-accessibility.spec.ts
?? tests/e2e/run-lifecycle.spec.ts
?? tests/e2e/teardown.ts
?? tests/fixtures/research-eval.json
?? tests/live-auth-checks.mjs
?? tests/live-runs-checks.mjs
?? tests/operation-input.types.ts
```

## Subsequent T29 slice (2026-10-01 HK)

Commit `1f348666e913a275249803daab0654ac75029fcf` contains these 13 paths. The following documentation checkpoint separately records the direct human FIMMICK/admin confirmation and precise verification boundaries.

```text
.github/workflows/buyeros-ci.yml
features/live/buyer-results.tsx
features/live/locale.ts
playwright.live-zoom.config.ts
tests/e2e/api-browser-zoom.spec.ts
tests/e2e/daily-workbench.spec.ts
tests/e2e/fixtures/workbench-auth.ts
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-en.json
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-en-buyers.png
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-en-operations.png
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-zh-HK.json
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-zh-HK-buyers.png
artifacts/t29-screenshots/t29-api-fixture-actual-zoom-20261001-zh-HK-operations.png
```

## Subsequent T30 full continuity slice — 2026-10-01 HK

Starting source479141f5f04455cdc19c786cb40a3a0fd9f4b4d2; author-reviewed current slice below. Source SHA is recorded in the final handoff after commit. Earlier path inventories remain historical.

```text
.github/workflows/buyeros-ci.yml
artifacts/t30-local-test-output-20261001.txt
artifacts/t30-production-metadata-20261001.json
artifacts/t30-screenshots/t30-continuity-en-desktop-approved-export-fixture.png
artifacts/t30-screenshots/t30-continuity-en-desktop-mobile-readback-fixture.png
artifacts/t30-screenshots/t30-continuity-en-desktop-outcome-fixture.png
artifacts/t30-screenshots/t30-continuity-en-mobile-approved-export-fixture.png
artifacts/t30-screenshots/t30-continuity-en-mobile-mobile-readback-fixture.png
artifacts/t30-screenshots/t30-continuity-en-mobile-outcome-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-desktop-approved-export-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-desktop-mobile-readback-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-desktop-outcome-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-mobile-approved-export-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-mobile-mobile-readback-fixture.png
artifacts/t30-screenshots/t30-continuity-zh-HK-mobile-outcome-fixture.png
artifacts/t30-tests/api-actual-zoom-required-20261001.xml
artifacts/t30-tests/api-required-20261001.xml
artifacts/t30-tests/bilingual-continuity-desktop-20261001.xml
artifacts/t30-tests/buyer-management-required-20261001.xml
artifacts/t30-tests/buyer-pagination-required-20261001.xml
artifacts/t30-tests/continuity-all-layouts-20261001.xml
artifacts/t30-tests/original-acceptance-required-20261001.xml
artifacts/t30-tests/rollback-guards-20261001.xml
artifacts/t30-tests/workbench-required-20261001.xml
artifacts/t30-tests/worker-required-20261001.xml
artifacts/t30-verification-20261001.json
docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md
docs/buyeros/RELEASE_READINESS.md
docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
docs/buyeros/T30_RELEASE_CANDIDATE_HANDOFF_20261001.md
docs/buyeros/remaining/API_OPERATION_STATUS.csv
docs/buyeros/remaining/CHANGED_FILES.md
docs/buyeros/remaining/TASKS.json
docs/buyeros/runbooks/release.md
features/live/buyer-detail.tsx
features/live/buyer-management-controls.tsx
features/live/buyer-results.tsx
features/live/drafts.tsx
features/live/locale.ts
features/live/workspace-picker.tsx
services/api/buyeros_api/api/routes/buyers.py
services/api/buyeros_api/services/approval_service.py
services/api/buyeros_api/services/buyer_read.py
services/api/buyeros_api/services/buyer_view.py
services/api/buyeros_api/services/draft_service.py
services/api/tests/test_draft_approval_context_db.py
services/api/tests/test_draft_approval_migration.py
services/api/tests/test_draft_persistence_db.py
services/api/tools/serve_e2e_fixture.py
services/live/profile.ts
services/worker/buyeros_worker/handlers/draft_generate.py
services/worker/tests/fixtures/prepare_browser_project.py
services/worker/tests/test_grounded_drafts.py
tests/e2e/buyer-management.spec.ts
tests/e2e/daily-workbench.spec.ts
tests/e2e/fixtures/workbench-auth.ts
tests/e2e/mvp-a-research.spec.ts
tests/live-adapter-checks.mjs
```

## T30 publication evidence checkpoint

Application/test commit41810627540dd52c4567f853ae65d51e2bb6365d above has58 paths and six-job CI success. This following checkpoint changes only documentation/evidence, including the current hosted zoom files. No application/schema/owner approval change.

```text
artifacts/t30-hosted-ci-20261001.json
artifacts/t30-preview-metadata-4181062.json
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-en-buyers.png
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-en-operations.png
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-en.json
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-zh-HK-buyers.png
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-zh-HK-operations.png
artifacts/t30-screenshots/t30-hosted-api-actual-zoom-4181062-zh-HK.json
artifacts/t30-verification-20261001.json
docs/buyeros/RELEASE_READINESS.md
docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
docs/buyeros/T30_RELEASE_CANDIDATE_HANDOFF_20261001.md
docs/buyeros/remaining/CHANGED_FILES.md
docs/buyeros/remaining/TASKS.json
docs/buyeros/runbooks/release.md
```

## T30 published-checkpoint reconciliation

Documentation/evidence only: preserve reviewed application source4181062 and deployed source62d40bc. Correct the stale unpublished-CI and T30-fixture-pending descriptions; retain fresh six-job success metadata for documentation head326de15. No application, migration, owner approval or activation change.

```text
artifacts/t30-ci-head-checkpoint-20261001.json
docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
docs/buyeros/T30_RELEASE_CANDIDATE_HANDOFF_20261001.md
docs/buyeros/remaining/CHANGED_FILES.md
docs/buyeros/remaining/TASKS.json
```

## T30 specifically authorized production rollout checkpoint

Documentation/evidence only after deploying reviewed application source4181062 to the existing production Vercel project. Five new artifacts preserve sanitized preflight, deployment source/alias readback, standalone four-GET acceptance, exact results and bounded error counts. Six existing documents track current deployment, refreshed human FIMMICK/admin visibility and remaining external gates. No domain application/schema/owner approval changed; per-operation authorized deployment success is not inferred from anonymous HTTP checks.

```text
artifacts/t30-production-preflight-4181062-20261001.json
artifacts/t30-production-deployment-4181062-20261001.json
artifacts/t30-production-acceptance-4181062-20261001.mjs
artifacts/t30-production-acceptance-4181062-20261001.json
artifacts/t30-production-error-scan-4181062-20261001.json
docs/buyeros/RELEASE_READINESS.md
docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
docs/buyeros/T30_RELEASE_CANDIDATE_HANDOFF_20261001.md
docs/buyeros/remaining/CHANGED_FILES.md
docs/buyeros/remaining/TASKS.json
docs/buyeros/runbooks/release.md
```
