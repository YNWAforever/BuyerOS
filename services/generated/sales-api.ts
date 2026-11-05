/** Generated sales extension; run node scripts/generate-sales-api.mjs --write. */

export interface paths {
    "/workspaces/{workspace_id}/projects/{project_id}/sales/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["listSalesSkills"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current thread ACL precedes count/pagination. Stable message_sequence/id order. Authored intake recovery remains available when admission is disabled. */
        get: operations["listSalesTasks"];
        put?: never;
        /** @description Create bounded partial intake under a current thread If-Match. Supplied values remain strictly typed; missing inputs persist as Needs input. Complete arguments permit a review plan only, never model/provider execution. */
        post: operations["createSalesTask"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["getSalesTask"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["listSalesTaskEvents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. Cancellation has no body; If-Match is the sole task revision precondition. */
        post: operations["cancelSalesTask"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List latest visible outputs, optionally linked to the selected native record. Apply output/source ACLs before pagination and totals; never disclose private-thread backlinks. Paired native_surface/native_id required; invalid filter is 422 INVALID_REQUEST. No content retrieval bypass. */
        get: operations["listSalesOutputs"];
        put?: never;
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        post: operations["saveSalesOutput"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/versions/{revision}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["getSalesOutputRevision"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["listSalesOutputVersions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/regenerate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        post: operations["regenerateSalesOutput"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        post: operations["exportSalesReport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Authenticated current workspace/project authority. Admin-only assignment, rotation and disconnect; native If-Match binds connection.version, expected_generation binds credential generation. Replays reauthorize and return current sanitized metadata. 503 until Task8 connection schema is installed; live OAuth provider remains disabled. */
        get: operations["listXverumConnections"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/connections/{connection_id}/assignment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** @description Authenticated current workspace/project authority. Admin-only assignment, rotation and disconnect; native If-Match binds connection.version, expected_generation binds credential generation. Replays reauthorize and return current sanitized metadata. 503 until Task8 connection schema is installed; live OAuth provider remains disabled. */
        put: operations["assignXverumConnection"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/connections/{connection_id}/disconnect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Authenticated current workspace/project authority. Admin-only assignment, rotation and disconnect; native If-Match binds connection.version, expected_generation binds credential generation. Replays reauthorize and return current sanitized metadata. 503 until Task8 connection schema is installed; live OAuth provider remains disabled. */
        post: operations["disconnectXverumConnection"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/quotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Authenticated actor/project-scoped staged Xverum admission and readback. Five-minute immutable quote fingerprint binds selection, generation, buyer version and administrator USD tariff. Confirmation reserves integer credits and separate USD liability; Confirmation atomically creates the native staged dispatch outbox. Durable claims precede provider IO. Reads remain available with entry disabled. */
        post: operations["createXverumQuote"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/quotes/{quote_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Authenticated actor/project-scoped staged Xverum admission and readback. Five-minute immutable quote fingerprint binds selection, generation, buyer version and administrator USD tariff. Confirmation reserves integer credits and separate USD liability; Task9 owns dispatch. Reads remain available with entry disabled. */
        get: operations["getXverumQuote"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/quotes/{quote_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Authenticated actor/project-scoped staged Xverum admission and readback. Five-minute immutable quote fingerprint binds selection, generation, buyer version and administrator USD tariff. Confirmation reserves integer credits and separate USD liability; Confirmation atomically creates the native staged dispatch outbox. Durable claims precede provider IO. Reads remain available with entry disabled. */
        post: operations["approveXverumQuote"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/receipts/{receipt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Authenticated actor/project-scoped staged Xverum admission and readback. Five-minute immutable quote fingerprint binds selection, generation, buyer version and administrator USD tariff. Confirmation reserves integer credits and separate USD liability; Task9 owns dispatch. Reads remain available with entry disabled. */
        get: operations["getXverumReceipt"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["getSalesOutput"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/followups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Owner/editor follows up on the same task using current task If-Match and actor-bound idempotency. Supplied arguments are strictly validated against the stored skill; missing fields remain Needs input. Optional source_refs replaces the selection. History is bounded to original plus 32 follow-ups. This recovery mutation never dispatches and remains available when admission is disabled. */
        post: operations["followupSalesTask"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * approveSalesStep
         * @description Requires enabled sales admission. Records explicit approval bound to the current task revision, sources, configuration and preview fingerprint. Does not dispatch.
         */
        post: operations["approveSalesStep"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/steps": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read admitted steps without dispatch
         * @description Current task ACL is rechecked. Read-only execution recovery remains available when new admission is disabled.
         */
        get: operations["listSalesSteps"];
        put?: never;
        /**
         * admitSalesStep
         * @description Requires enabled sales admission and current explicit execution approval. Reserves aggregate model liability and admits bounded durable execution; may dispatch model work. Idempotent replay is not new approval.
         */
        post: operations["admitSalesStep"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/execution-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview the current execution scope and maximum cost without approving or dispatching
         * @description Requires enabled sales admission, current editable task/source authority and an eligible selected model registration. Computes bounded execution liability without dispatch; unavailable when admission is disabled.
         */
        post: operations["previewSalesExecution"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/native-actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Explicit DB-only native buyer note, list membership or draft edit from an authorized saved output. Recheck current scope, sources, native permission and revision; deduplicate and atomically append a linked authored revision. No sending, provider call or approval. */
        post: operations["applySalesNativeAction"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current-authority exact/latest output rendered as an inert Markdown subset. No authored HTML, images or executable links; sandbox CSP and no-store. */
        get: operations["previewSalesOutput"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/output-review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Authorized complete assembly for explicit save review, including destination project/thread and private-by-default thread audience. Does not mark completion. */
        get: operations["reviewSalesOutput"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/connections/{connection_id}/rotate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Authenticated current workspace/project authority. Admin-only assignment, rotation and disconnect; native If-Match binds connection.version, expected_generation binds credential generation. Replays reauthorize and return current sanitized metadata. 503 until Task8 connection schema is installed; live OAuth provider remains disabled. */
        post: operations["rotateXverumConnection"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/receipts/{receipt_id}/reconcile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Current authority, receipt revision and native idempotency required. No provider IO or retry. Unknown evidence retains both holds; reconciliation uses exact per-tool authoritative evidence. */
        post: operations["reconcileXverumReceipt"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/receipts/{receipt_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Current authority, receipt revision and native idempotency required. No provider IO or retry. Unknown evidence retains both holds; reconciliation uses exact per-tool authoritative evidence. */
        post: operations["cancelXverumReceipt"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/receipts/{receipt_id}/liability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current operational authority can inspect content-free original account, connection, per-tool claims and liabilities without private-thread access. No projected contact data. */
        get: operations["getXverumLiability"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/tasks/{task_id}/quotes/{quote_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Admit a separately approved stage into the current authorized private task, binding exact task revision/context and shared invocation limits. A standalone receipt cannot be relinked. */
        post: operations["approveLinkedXverumQuote"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/enrichment-proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Extension contract only. Server derives actor and scope, rechecks current permissions and source eligibility. Mutations bind idempotency key and expected revisions; schema validity never grants authority. */
        get: operations["getEnrichmentProposal"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/enrichment-proposals/{proposal_id}/apply": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Explicit field review, current native permission and exact buyer If-Match. Replay reauthorizes the committed native/output revision. No automatic approval, sending or provider dispatch. */
        post: operations["applyEnrichmentProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/enrichment-proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Server trusted producer from selected settled detail receipts. Optional current contacts task saves a thread-private canonical proposal. Original private search authority is retained. */
        post: operations["createEnrichmentProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/core-guidance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Typed explicit native destination; no implicit provider admission. Consume native result through versioned followupSalesTask source selection. */
        get: operations["getSalesCoreGuidance"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/{task_id}/core-preparation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Explicit DB-only core/document producer, or preserved grounded model sections. No caller candidate; current native authority and exact selected sources, task CAS, idempotent canonical output. */
        post: operations["prepareSalesCoreOutput"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/formal-draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Explicit eligible recipient and exact saved preparation revision. Native grounded-template admission and DB-only materialization; no approval, delivery or schedule. */
        post: operations["createSalesFormalDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Explicit actor approval of the exact saved revision and format; native expiring export manifest, audit and current-authority download. Does not approve a native draft. */
        post: operations["exportSalesOutput"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/receipts/{receipt_id}/candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read only terminal retained search candidates after current receipt, task, source, connection, policy and expiry checks. No raw provider response or dispatch. */
        get: operations["getXverumCandidates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-outputs/{output_id}/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current-authorized output read and private thread role check. Returns only edit capability, never private thread identifiers. Mutation endpoints independently recheck authority. */
        get: operations["getSalesOutputPermissions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/xverum/tasks/{task_id}/stages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read admitted steps without dispatch
         * @description Read-only actor-owned linked lookup stage recovery after current task and receipt authority checks. Never dispatch or infer a fresh approval. At most sixteen bounded stages.
         */
        get: operations["listXverumTaskStages"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/capability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current authorized read; no admission or provider dispatch. */
        get: operations["getSalesCapability"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workspaces/{workspace_id}/projects/{project_id}/sales-tasks/native-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Current authorized read; no admission or provider dispatch. */
        get: operations["listSalesNativeSources"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActionProposal */
        ActionProposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Capability
             * @enum {string}
             */
            capability: "search_company_xverum" | "search_people_xverum" | "enrich_company_xverum" | "enrich_person_xverum" | "get_email_xverum" | "research.read" | "profile.propose" | "buyers.review" | "lists.propose" | "drafts.prepare" | "documents.read" | "documents.prepare" | "reports.read" | "reports.export" | "tasks.plan";
            /** Arguments */
            arguments: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Source Versions */
            source_versions: components["schemas"]["SourceRef"][];
        } & ({
            /** @constant */
            capability: "search_company_xverum";
            arguments: components["schemas"]["SearchArguments"];
        } | {
            /** @constant */
            capability: "search_people_xverum";
            arguments: components["schemas"]["SearchArguments"];
        } | {
            /** @constant */
            capability: "enrich_company_xverum";
            arguments: components["schemas"]["CompanyDetailArguments"];
        } | {
            /** @constant */
            capability: "enrich_person_xverum";
            arguments: components["schemas"]["PersonDetailArguments"];
        } | {
            /** @constant */
            capability: "get_email_xverum";
            arguments: components["schemas"]["PersonDetailArguments"];
        } | {
            /** @constant */
            capability: "research.read";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "profile.propose";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "buyers.review";
            arguments: components["schemas"]["BuyerNativeArguments"];
        } | {
            /** @constant */
            capability: "lists.propose";
            arguments: components["schemas"]["ListNativeArguments"];
        } | {
            /** @constant */
            capability: "drafts.prepare";
            arguments: components["schemas"]["DraftNativeArguments"];
        } | {
            /** @constant */
            capability: "documents.read";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "documents.prepare";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "reports.read";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "reports.export";
            arguments: components["schemas"]["NativeActionArguments"];
        } | {
            /** @constant */
            capability: "tasks.plan";
            arguments: components["schemas"]["NativeActionArguments"];
        });
        /** AgendaItem */
        AgendaItem: {
            /** Topic */
            topic: string;
            /** Minutes */
            minutes: number;
        };
        /** AssessmentDimension */
        AssessmentDimension: {
            /**
             * Dimension
             * @enum {string}
             */
            dimension: "budget" | "authority" | "need" | "timeline" | "metrics" | "economic_buyer" | "decision_criteria" | "decision_process" | "pain" | "champion";
            /** Score */
            score: number | null;
            /** Rationale */
            rationale: string;
            /** Evidence */
            evidence: components["schemas"]["SourceRef"][];
        };
        /** AuthoredContent */
        AuthoredContent: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
        };
        /** BuyerArguments */
        BuyerArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
        };
        /** BuyerNativeArguments */
        BuyerNativeArguments: {
            /** Refs */
            refs: components["schemas"]["NativeRef"][];
            /** Purpose */
            purpose: string;
            /** @default null */
            output: components["schemas"]["OutputDependency"] | null;
            /** @default null */
            mutation: components["schemas"]["BuyerNoteMutation"] | null;
        };
        /** BuyerNoteMutation */
        BuyerNoteMutation: {
            /** Note */
            note: string;
        };
        /** BuyerReview */
        BuyerReview: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Assessments */
            assessments: components["schemas"]["Finding"][];
            /** Proposed Buyer Ids */
            proposed_buyer_ids: string[];
            /**
             * Review Required
             * @default true
             * @constant
             */
            review_required: true;
        };
        /** CommercialTerms */
        CommercialTerms: {
            price: components["schemas"]["Money"];
            /** Scope */
            scope: string;
            /** Exclusions */
            exclusions: string;
            /** Timeline */
            timeline: string;
            /** Evidence */
            evidence: components["schemas"]["SourceRef"][];
        };
        /** CompanyDetailArguments */
        CompanyDetailArguments: {
            /** Company Id */
            company_id: string;
        };
        /** CompetitiveDocument */
        CompetitiveDocument: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Competitors */
            competitors: components["schemas"]["Finding"][];
            /** Strengths */
            strengths: components["schemas"]["Finding"][];
            /** Gaps */
            gaps: components["schemas"]["Finding"][];
            /** Switching Costs */
            switching_costs: string[];
        };
        /** CompetitorsArguments */
        CompetitorsArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /**
             * Competitor Names
             * @default []
             */
            competitor_names: string[];
        };
        /** ConnectionAssignment */
        ConnectionAssignment: {
            /** Project Ids */
            project_ids: string[];
            /** Expected Generation */
            expected_generation: number;
        };
        /** ConnectionBinding */
        ConnectionBinding: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Generation */
            generation: number;
            /** Version */
            version: number;
            /** Account Ref */
            account_ref: string;
            /** Tariff Version */
            tariff_version: string;
            /**
             * Status
             * @enum {string}
             */
            status: "configuration_required" | "connected" | "expired" | "disconnected";
            /** Project Ids */
            project_ids: string[];
        };
        /** ConnectionBindingResponse */
        ConnectionBindingResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["ConnectionBinding"];
        };
        /** ConnectionPage */
        ConnectionPage: {
            /** Connections */
            connections: components["schemas"]["ConnectionBinding"][];
        };
        /** ConnectionPageResponse */
        ConnectionPageResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["ConnectionPage"];
        };
        /** ConnectionRotation */
        ConnectionRotation: {
            /** Expected Generation */
            expected_generation: number;
        };
        /** ContactsArguments */
        ContactsArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /** Purpose */
            purpose: string;
            /** Roles */
            roles: string[];
        };
        /** ContextSnapshot */
        ContextSnapshot: {
            /** Refs */
            refs: components["schemas"]["SourceRef"][];
            /** Digest */
            digest: string;
            /** Profile Version */
            profile_version: number | null;
            /** Connection Generations */
            connection_generations?: {
                [key: string]: number;
            };
        };
        /** CoreDestination */
        CoreDestination: {
            /**
             * Operation Id
             * @enum {string}
             */
            operation_id: "startRun" | "getProject" | "generateDraft" | "changeListMemberships";
            /**
             * Workspace Id
             * Format: uuid
             */
            workspace_id: string;
            /**
             * Project Id
             * Format: uuid
             */
            project_id: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /**
             * Requires Human Review
             * @default true
             * @constant
             */
            requires_human_review: true;
            /** Idempotency Key */
            idempotency_key: string;
            /**
             * Result Followup Operation
             * @default followupSalesTask
             * @constant
             */
            result_followup_operation: "followupSalesTask";
        };
        /** CoreGuidance */
        CoreGuidance: {
            /**
             * State
             * @enum {string}
             */
            state: "needs_input" | "ready_for_review";
            /** Missing Inputs */
            missing_inputs: string[];
            action: components["schemas"]["CoreDestination"];
            work: components["schemas"]["CoreWork"];
        };
        /** CoreGuidanceResponse */
        CoreGuidanceResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["CoreGuidance"];
        };
        /** CoreWork */
        CoreWork: {
            /** Steps */
            steps: number;
            /**
             * Model Calls
             * @constant
             */
            model_calls: 0;
            /**
             * Provider Calls
             * @constant
             */
            provider_calls: 0;
            /**
             * Max Concurrent Steps
             * @constant
             */
            max_concurrent_steps: 1;
            /**
             * Model Liability Usd
             * @constant
             */
            model_liability_usd: "0";
            /** Native Provider Liability */
            native_provider_liability: string;
            /** Discovery */
            discovery: string;
        };
        /** DocumentUnderstanding */
        DocumentUnderstanding: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Document Ids */
            document_ids: string[];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            /**
             * Extraction Status
             * @enum {string}
             */
            extraction_status: "complete" | "partial" | "unavailable";
            /**
             * Document Basis
             * @default []
             */
            document_basis: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
            /**
             * Extracted Passages
             * @default []
             */
            extracted_passages: string[];
            /**
             * Question
             * @default null
             */
            question: string | null;
        };
        /** DocumentsArguments */
        DocumentsArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /** Document Ids */
            document_ids: string[];
            /** Question */
            question: string;
        };
        /** DraftMutation */
        DraftMutation: {
            /** Subject */
            subject: string;
            /** Body */
            body: string;
        };
        /** DraftNativeArguments */
        DraftNativeArguments: {
            /** Refs */
            refs: components["schemas"]["NativeRef"][];
            /** Purpose */
            purpose: string;
            /** @default null */
            output: components["schemas"]["OutputDependency"] | null;
            /** @default null */
            mutation: components["schemas"]["DraftMutation"] | null;
        };
        /** EnrichmentApply */
        EnrichmentApply: {
            /**
             * Proposal Id
             * Format: uuid
             */
            proposal_id: string;
            /** Buyer Version */
            buyer_version: number;
            /** Selected Fields */
            selected_fields: ("company_name" | "domain" | "industry" | "location" | "employee_count" | "person_name" | "job_title" | "employer" | "business_email")[];
        };
        /** EnrichmentCreate */
        EnrichmentCreate: {
            /**
             * Selected Id
             * @default null
             */
            selected_id: string | null;
            /**
             * Previous Proposal Id
             * @default null
             */
            previous_proposal_id: string | null;
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /** Receipt Ids */
            receipt_ids: string[];
            /**
             * Task Id
             * @default null
             */
            task_id: string | null;
        };
        /** EnrichmentProposal */
        EnrichmentProposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /** Buyer Version */
            buyer_version: number;
            /**
             * Identity Match
             * @enum {string}
             */
            identity_match: "resolved" | "ambiguous" | "conflicting" | "unresolved";
            /** Fields */
            fields: components["schemas"]["FieldChoice"][];
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
        };
        /** EnrichmentProposalResponse */
        EnrichmentProposalResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["EnrichmentProposal"];
        };
        /** ErrorPayload */
        ErrorPayload: {
            /**
             * Code
             * @enum {string}
             */
            code: "configuration_required" | "source_unavailable" | "permission_revoked" | "stale_revision" | "budget_exhausted" | "provider_unavailable" | "invalid_output" | "outcome_unknown";
            /** Retryable */
            retryable: boolean;
        };
        /**
         * ErrorResponse
         * @description Native api.errors.error_body shape, including validation/server errors.
         */
        ErrorResponse: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Request Id */
            request_id: string;
            /** Retryable */
            retryable: boolean;
        };
        /** EventPage */
        EventPage: {
            /** Events */
            events: components["schemas"]["TaskEvent"][];
            /** Next Sequence */
            next_sequence: number | null;
        };
        /** EventPageResponse */
        EventPageResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["EventPage"];
        };
        /** ExecutionBounds */
        ExecutionBounds: {
            /**
             * Max Steps
             * @default 16
             */
            max_steps: number;
            /**
             * Max Model Calls
             * @default 8
             */
            max_model_calls: number;
            /**
             * Max Concurrent Steps
             * @default 2
             */
            max_concurrent_steps: number;
            /**
             * Automatic Model Repair
             * @default false
             * @constant
             */
            automatic_model_repair: false;
        };
        /** ExecutionPreview */
        ExecutionPreview: {
            /** Model Id */
            model_id: string;
            /** Route */
            route: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Revision */
            revision: number;
            /** Fingerprint */
            fingerprint: string;
            /** Max Calls */
            max_calls: number;
            /** Max Concurrency */
            max_concurrency: number;
            /** Max Liability Usd */
            max_liability_usd: number | string;
        };
        /** ExecutionPreviewResponse */
        ExecutionPreviewResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["ExecutionPreview"];
        };
        /** ExecutionReview */
        ExecutionReview: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Revision */
            revision: number;
            /** Fingerprint */
            fingerprint: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Max Calls */
            max_calls: number;
            /** Max Concurrency */
            max_concurrency: number;
            /** Max Liability Usd */
            max_liability_usd: number | string;
        };
        /** ExecutionReviewResponse */
        ExecutionReviewResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["ExecutionReview"];
        };
        /** ExportArguments */
        ExportArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Output Id
             * Format: uuid
             */
            output_id: string;
            /** Output Revision */
            output_revision: number;
            /**
             * Export Id
             * @default null
             */
            export_id: string | null;
        };
        /** FieldChoice */
        FieldChoice: {
            /**
             * Field
             * @enum {string}
             */
            field: "company_name" | "domain" | "industry" | "location" | "employee_count" | "person_name" | "job_title" | "employer" | "business_email";
            /** Existing Value */
            existing_value: string | number | null;
            /** Proposed Value */
            proposed_value: string | number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "proposed" | "conflict" | "unknown";
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
            /**
             * Retrieved At
             * Format: date-time
             */
            retrieved_at: string;
            /** Provider Freshness */
            provider_freshness: string | null;
        };
        /** Finding */
        Finding: {
            /** Statement */
            statement: string;
            /** Evidence */
            evidence: components["schemas"]["SourceRef"][];
            /**
             * Confidence
             * @enum {string}
             */
            confidence: "high" | "medium" | "low" | "inference";
            /**
             * Observed At
             * @default null
             */
            observed_at: string | null;
        };
        /** FollowupArguments */
        FollowupArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /**
             * Recipient Id
             * @default null
             */
            recipient_id: string | null;
            /** Objective */
            objective: string;
            /**
             * Framework
             * @default direct
             * @enum {string}
             */
            framework: "PAS" | "AIDA" | "BAB" | "direct";
            interaction_ref: components["schemas"]["SourceRef"];
            /**
             * Scenario
             * @enum {string}
             */
            scenario: "post_meeting" | "post_demo" | "post_proposal" | "recovery" | "nurture";
        };
        /** FollowupPreparation */
        FollowupPreparation: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Scenario
             * @enum {string}
             */
            scenario: "post_meeting" | "post_demo" | "post_proposal" | "recovery" | "nurture";
            interaction_ref: components["schemas"]["SourceRef"];
            /** Messages */
            messages: components["schemas"]["PreparedMessage"][];
            /**
             * Review Required
             * @default true
             * @constant
             */
            review_required: true;
        };
        /** FormalDraftInput */
        FormalDraftInput: {
            /**
             * Recipient Id
             * Format: uuid
             */
            recipient_id: string;
            /** Expected Revision */
            expected_revision: number;
        };
        /** ICPArguments */
        ICPArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /** Offer Description */
            offer_description: string;
            /**
             * Profile Id
             * @default null
             */
            profile_id: string | null;
        };
        /** CompetitorsArguments */
        IntakeCompetitorsArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Competitor Names */
            competitor_names?: string[];
        };
        /** ContactsArguments */
        IntakeContactsArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /** Purpose */
            purpose?: string;
            /** Roles */
            roles?: string[];
        };
        /** DocumentsArguments */
        IntakeDocumentsArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Document Ids */
            document_ids?: string[];
            /** Question */
            question?: string;
        };
        /** IntakeEntry */
        IntakeEntry: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
            /** User Message */
            user_message: string;
            /** Arguments */
            arguments: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Source Refs
             * @default []
             */
            source_refs: components["schemas"]["SourceRef"][];
        };
        /** ExportArguments */
        IntakeExportArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Output Id
             * Format: uuid
             */
            output_id?: string;
            /** Output Revision */
            output_revision?: number;
            /** Export Id */
            export_id?: string | null;
        };
        /** FollowupArguments */
        IntakeFollowupArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Recipient Id */
            recipient_id?: string | null;
            /** Objective */
            objective?: string;
            /**
             * Framework
             * @enum {string}
             */
            framework?: "PAS" | "AIDA" | "BAB" | "direct";
            interaction_ref?: components["schemas"]["IntakeValueSourceRef"];
            /**
             * Scenario
             * @enum {string}
             */
            scenario?: "post_meeting" | "post_demo" | "post_proposal" | "recovery" | "nurture";
        };
        /** ICPArguments */
        IntakeICPArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Offer Description */
            offer_description?: string;
            /** Profile Id */
            profile_id?: string | null;
        };
        /** MeetingArguments */
        IntakeMeetingArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Meeting At
             * Format: date-time
             */
            meeting_at?: string;
            /** Objective */
            objective?: string;
            /** Attendee Ids */
            attendee_ids?: string[];
            /**
             * Duration Minutes
             * @enum {integer}
             */
            duration_minutes?: 30 | 60;
        };
        /** ObjectionsArguments */
        IntakeObjectionsArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Buyer Id */
            buyer_id?: string | null;
            /** Objections */
            objections?: string[];
        };
        /** OutreachArguments */
        IntakeOutreachArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Recipient Id */
            recipient_id?: string | null;
            /** Objective */
            objective?: string;
            /**
             * Framework
             * @enum {string}
             */
            framework?: "PAS" | "AIDA" | "BAB" | "direct";
        };
        /** ProjectArguments */
        IntakeProjectArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Offer Description */
            offer_description?: string;
            /** Buyer Id */
            buyer_id?: string | null;
            /** Recipient Id */
            recipient_id?: string | null;
        };
        /** ProposalArguments */
        IntakeProposalArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Pain Points */
            pain_points?: string[];
            /** Terms */
            terms?: components["schemas"]["IntakeValueCommercialTerms"][];
            /** Case Study Refs */
            case_study_refs?: components["schemas"]["IntakeValueSourceRef"][];
        };
        /** ProspectArguments */
        IntakeProspectArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /** Objective */
            objective?: string;
            bounds?: components["schemas"]["IntakeValueExecutionBounds"];
        };
        /** QualificationArguments */
        IntakeQualificationArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id?: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Profile Version */
            profile_version?: number;
            /**
             * Rubric
             * @constant
             */
            rubric?: "BANT_MEDDIC";
        };
        /** QuickArguments */
        IntakeQuickArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Buyer Id */
            buyer_id?: string | null;
            /** Research Question */
            research_question?: string | null;
            /** Max Sources */
            max_sources?: number;
        };
        /** ReportArguments */
        IntakeReportArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /**
             * As Of
             * Format: date-time
             */
            as_of?: string;
            /** Buyer Ids */
            buyer_ids?: string[];
            /** List Id */
            list_id?: string | null;
        };
        /** ResearchArguments */
        IntakeResearchArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Buyer Id */
            buyer_id?: string | null;
            /** Research Question */
            research_question?: string | null;
            /** Max Sources */
            max_sources?: number;
        };
        /** ReviewArguments */
        IntakeReviewArguments: {
            /**
             * Language
             * @enum {string}
             */
            language?: "en" | "zh-HK";
            /** Buyer Ids */
            buyer_ids?: string[];
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id?: string;
            /** Profile Version */
            profile_version?: number;
        };
        /** CommercialTerms */
        IntakeValueCommercialTerms: {
            price: components["schemas"]["IntakeValueMoney"];
            /** Scope */
            scope: string;
            /** Exclusions */
            exclusions: string;
            /** Timeline */
            timeline: string;
            /** Evidence */
            evidence: components["schemas"]["IntakeValueSourceRef"][];
        };
        /** ExecutionBounds */
        IntakeValueExecutionBounds: {
            /** Max Steps */
            max_steps?: number;
            /** Max Model Calls */
            max_model_calls?: number;
            /** Max Concurrent Steps */
            max_concurrent_steps?: number;
            /**
             * Automatic Model Repair
             * @constant
             */
            automatic_model_repair?: false;
        };
        /** Money */
        IntakeValueMoney: {
            /** Amount */
            amount: number | string;
            /** Currency */
            currency: string;
        };
        /** SourceRef */
        IntakeValueSourceRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Version */
            version: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "project_fact" | "profile" | "buyer" | "document" | "output" | "run" | "provider_evidence" | "drive";
            /** Locator */
            locator: string;
            /**
             * Retention Class
             * @enum {string}
             */
            retention_class: "durable" | "metadata_only" | "zero_content";
        };
        JsonValue: unknown;
        /** ListMutation */
        ListMutation: {
            /**
             * Operation
             * @enum {string}
             */
            operation: "add" | "remove";
            /** Buyers */
            buyers: components["schemas"]["NativeRef"][];
        };
        /** ListNativeArguments */
        ListNativeArguments: {
            /** Refs */
            refs: components["schemas"]["NativeRef"][];
            /** Purpose */
            purpose: string;
            /** @default null */
            output: components["schemas"]["OutputDependency"] | null;
            /** @default null */
            mutation: components["schemas"]["ListMutation"] | null;
        };
        /**
         * LiveResponse
         * @description Native api.errors.envelope metadata; data is typed by each response.
         */
        LiveResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
        };
        /** MeetingArguments */
        MeetingArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Meeting At
             * Format: date-time
             */
            meeting_at: string;
            /** Objective */
            objective: string;
            /**
             * Attendee Ids
             * @default []
             */
            attendee_ids: string[];
            /**
             * Duration Minutes
             * @default 30
             * @enum {integer}
             */
            duration_minutes: 30 | 60;
        };
        /** MeetingBrief */
        MeetingBrief: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Cheat Sheet */
            cheat_sheet: string;
            /** Attendees */
            attendees: components["schemas"]["Finding"][];
            /** Talking Points */
            talking_points: string[];
            /** Discovery Questions */
            discovery_questions: string[];
            /** Agenda */
            agenda: components["schemas"]["AgendaItem"][];
            /** Next Steps */
            next_steps: string[];
        };
        /** ModelUsage */
        ModelUsage: {
            /** Input Tokens */
            input_tokens: number;
            /** Output Tokens */
            output_tokens: number;
            cost: components["schemas"]["Money"] | null;
        };
        /** Money */
        Money: {
            /** Amount */
            amount: number | string;
            /** Currency */
            currency: string;
        };
        /** NativeActionArguments */
        NativeActionArguments: {
            /** Refs */
            refs: components["schemas"]["NativeRef"][];
            /** Purpose */
            purpose: string;
        };
        /** NativeEvidenceProof */
        NativeEvidenceProof: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Version */
            version: number;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /** Digest */
            digest: string;
            /** Excerpt */
            excerpt: string;
            /**
             * Stance
             * @enum {string}
             */
            stance: "supports" | "contradicts" | "qualifies" | "neutral";
            /** Is Inference */
            is_inference: boolean;
        };
        /** NativeRef */
        NativeRef: {
            /**
             * Surface
             * @enum {string}
             */
            surface: "profile" | "buyer" | "list" | "run" | "draft" | "document" | "export";
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
        };
        /** NativeRefResponse */
        NativeRefResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["NativeRef"];
        };
        /** ObjectionPlaybook */
        ObjectionPlaybook: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Responses */
            responses: components["schemas"]["ObjectionResponse"][];
        };
        /** ObjectionResponse */
        ObjectionResponse: {
            /** Objection */
            objection: string;
            /** Feel Felt Found */
            feel_felt_found: string;
            /** Acknowledge Bridge Close */
            acknowledge_bridge_close: string;
            /** Followup Question */
            followup_question: string;
            /** Walk Away Criteria */
            walk_away_criteria: string;
            /** Proof Points */
            proof_points: components["schemas"]["Finding"][];
        };
        /** ObjectionsArguments */
        ObjectionsArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /**
             * Buyer Id
             * @default null
             */
            buyer_id: string | null;
            /** Objections */
            objections: string[];
        };
        /** OutputCandidate */
        OutputCandidate: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "profile_proposal" | "research_report" | "qualification_assessment" | "enrichment_proposal" | "competitive_document" | "outreach_preparation" | "followup_preparation" | "meeting_brief" | "sales_proposal" | "objection_playbook" | "pipeline_report" | "report_export" | "project_setup" | "document_understanding" | "buyer_review";
            /** Content */
            content: components["schemas"]["ProfileProposal"] | components["schemas"]["ResearchReport"] | components["schemas"]["QualificationAssessment"] | components["schemas"]["EnrichmentProposal"] | components["schemas"]["CompetitiveDocument"] | components["schemas"]["OutreachPreparation"] | components["schemas"]["FollowupPreparation"] | components["schemas"]["MeetingBrief"] | components["schemas"]["SalesProposal"] | components["schemas"]["ObjectionPlaybook"] | components["schemas"]["PipelineReport"] | components["schemas"]["ReportExport"] | components["schemas"]["ProjectSetup"] | components["schemas"]["DocumentUnderstanding"] | components["schemas"]["BuyerReview"];
            /** Citations */
            citations: components["schemas"]["SourceRef"][];
            /** Dependencies */
            dependencies: components["schemas"]["OutputDependency"][];
            /** Native Refs */
            native_refs: components["schemas"]["NativeRef"][];
        } & ({
            /** @constant */
            kind: "profile_proposal";
            content: components["schemas"]["ProfileProposal"];
        } | {
            /** @constant */
            kind: "research_report";
            content: components["schemas"]["ResearchReport"];
        } | {
            /** @constant */
            kind: "qualification_assessment";
            content: components["schemas"]["QualificationAssessment"];
        } | {
            /** @constant */
            kind: "enrichment_proposal";
            content: components["schemas"]["EnrichmentProposal"];
        } | {
            /** @constant */
            kind: "competitive_document";
            content: components["schemas"]["CompetitiveDocument"];
        } | {
            /** @constant */
            kind: "outreach_preparation";
            content: components["schemas"]["OutreachPreparation"];
        } | {
            /** @constant */
            kind: "followup_preparation";
            content: components["schemas"]["FollowupPreparation"];
        } | {
            /** @constant */
            kind: "meeting_brief";
            content: components["schemas"]["MeetingBrief"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            content: components["schemas"]["SalesProposal"];
        } | {
            /** @constant */
            kind: "objection_playbook";
            content: components["schemas"]["ObjectionPlaybook"];
        } | {
            /** @constant */
            kind: "pipeline_report";
            content: components["schemas"]["PipelineReport"];
        } | {
            /** @constant */
            kind: "report_export";
            content: components["schemas"]["ReportExport"];
        } | {
            /** @constant */
            kind: "project_setup";
            content: components["schemas"]["ProjectSetup"];
        } | {
            /** @constant */
            kind: "document_understanding";
            content: components["schemas"]["DocumentUnderstanding"];
        } | {
            /** @constant */
            kind: "buyer_review";
            content: components["schemas"]["BuyerReview"];
        });
        /**
         * OutputCollectionPage
         * @description ACL-filtered latest outputs, distinct from a single output's version history.
         */
        OutputCollectionPage: {
            /** Items */
            items: components["schemas"]["OutputVersion"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** OutputCollectionResponse */
        OutputCollectionResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["OutputCollectionPage"];
        };
        /** OutputDependency */
        OutputDependency: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
        };
        /** OutputExportInput */
        OutputExportInput: {
            /** Revision */
            revision: number;
            /**
             * Format
             * @enum {string}
             */
            format: "markdown" | "pdf";
            /**
             * Approved
             * @constant
             */
            approved: true;
        };
        /** OutputListQuery */
        OutputListQuery: {
            /**
             * Native Surface
             * @default null
             */
            native_surface: ("profile" | "buyer" | "list" | "run" | "draft" | "document" | "export") | null;
            /**
             * Native Id
             * @default null
             */
            native_id: string | null;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /**
             * Limit
             * @default 50
             */
            limit: number;
        } & ({
            native_surface?: null;
            native_id?: null;
        } | {
            native_surface: string;
            /** Format: uuid */
            native_id: string;
        });
        /** OutputPage */
        OutputPage: {
            /** Outputs */
            outputs: components["schemas"]["OutputVersion"][];
            /** Next Revision */
            next_revision: number | null;
        };
        /** OutputPageResponse */
        OutputPageResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["OutputPage"];
        };
        /** OutputPayload */
        OutputPayload: {
            /**
             * Output Id
             * Format: uuid
             */
            output_id: string;
            /** Revision */
            revision: number;
        };
        /** OutputReadQuery */
        OutputReadQuery: {
            /**
             * Revision
             * @default null
             */
            revision: number | null;
        };
        /** OutputReview */
        OutputReview: {
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Task Revision */
            task_revision: number;
            /**
             * Project Id
             * Format: uuid
             */
            project_id: string;
            /**
             * Thread Id
             * Format: uuid
             */
            thread_id: string;
            /**
             * Visibility
             * @default thread
             * @constant
             */
            visibility: "thread";
            candidate: components["schemas"]["OutputCandidate"];
        };
        /** OutputReviewResponse */
        OutputReviewResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["OutputReview"];
        };
        /** OutputSave */
        OutputSave: {
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Expected Task Revision */
            expected_task_revision: number;
            /**
             * Visibility
             * @default thread
             * @enum {string}
             */
            visibility: "thread" | "project";
            candidate: components["schemas"]["OutputCandidate"];
        };
        /** OutputVersion */
        OutputVersion: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
            /**
             * Visibility
             * @enum {string}
             */
            visibility: "thread" | "project";
            /** Native Refs */
            native_refs: components["schemas"]["NativeRef"][];
            /**
             * Kind
             * @enum {string}
             */
            kind: "profile_proposal" | "research_report" | "qualification_assessment" | "enrichment_proposal" | "competitive_document" | "outreach_preparation" | "followup_preparation" | "meeting_brief" | "sales_proposal" | "objection_playbook" | "pipeline_report" | "report_export" | "project_setup" | "document_understanding" | "buyer_review";
            /** Content */
            content: components["schemas"]["ProfileProposal"] | components["schemas"]["ResearchReport"] | components["schemas"]["QualificationAssessment"] | components["schemas"]["EnrichmentProposal"] | components["schemas"]["CompetitiveDocument"] | components["schemas"]["OutreachPreparation"] | components["schemas"]["FollowupPreparation"] | components["schemas"]["MeetingBrief"] | components["schemas"]["SalesProposal"] | components["schemas"]["ObjectionPlaybook"] | components["schemas"]["PipelineReport"] | components["schemas"]["ReportExport"] | components["schemas"]["ProjectSetup"] | components["schemas"]["DocumentUnderstanding"] | components["schemas"]["BuyerReview"] | null;
            /** Citations */
            citations: components["schemas"]["SourceRef"][];
            /** Dependencies */
            dependencies: components["schemas"]["OutputDependency"][];
            /**
             * Availability
             * @enum {string}
             */
            availability: "available" | "source_deleted" | "permission_revoked" | "retention_expired" | "unavailable";
        } & (({
            /** @constant */
            availability?: "available";
        } & ({
            /** @constant */
            kind?: "profile_proposal";
            content?: components["schemas"]["ProfileProposal"];
        } | {
            /** @constant */
            kind?: "research_report";
            content?: components["schemas"]["ResearchReport"];
        } | {
            /** @constant */
            kind?: "qualification_assessment";
            content?: components["schemas"]["QualificationAssessment"];
        } | {
            /** @constant */
            kind?: "enrichment_proposal";
            content?: components["schemas"]["EnrichmentProposal"];
        } | {
            /** @constant */
            kind?: "competitive_document";
            content?: components["schemas"]["CompetitiveDocument"];
        } | {
            /** @constant */
            kind?: "outreach_preparation";
            content?: components["schemas"]["OutreachPreparation"];
        } | {
            /** @constant */
            kind?: "followup_preparation";
            content?: components["schemas"]["FollowupPreparation"];
        } | {
            /** @constant */
            kind?: "meeting_brief";
            content?: components["schemas"]["MeetingBrief"];
        } | {
            /** @constant */
            kind?: "sales_proposal";
            content?: components["schemas"]["SalesProposal"];
        } | {
            /** @constant */
            kind?: "objection_playbook";
            content?: components["schemas"]["ObjectionPlaybook"];
        } | {
            /** @constant */
            kind?: "pipeline_report";
            content?: components["schemas"]["PipelineReport"];
        } | {
            /** @constant */
            kind?: "report_export";
            content?: components["schemas"]["ReportExport"];
        } | {
            /** @constant */
            kind?: "project_setup";
            content?: components["schemas"]["ProjectSetup"];
        } | {
            /** @constant */
            kind?: "document_understanding";
            content?: components["schemas"]["DocumentUnderstanding"];
        } | {
            /** @constant */
            kind?: "buyer_review";
            content?: components["schemas"]["BuyerReview"];
        })) | {
            /** @enum {unknown} */
            availability?: "source_deleted" | "permission_revoked" | "retention_expired" | "unavailable";
            content?: null;
            citations?: unknown;
            dependencies?: unknown;
            native_refs?: unknown;
        });
        /** OutputVersionResponse */
        OutputVersionResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["OutputVersion"];
        };
        /** OutreachArguments */
        OutreachArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /**
             * Recipient Id
             * @default null
             */
            recipient_id: string | null;
            /** Objective */
            objective: string;
            /**
             * Framework
             * @default direct
             * @enum {string}
             */
            framework: "PAS" | "AIDA" | "BAB" | "direct";
        };
        /** OutreachPreparation */
        OutreachPreparation: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Framework
             * @enum {string}
             */
            framework: "PAS" | "AIDA" | "BAB" | "direct";
            /** Messages */
            messages: components["schemas"]["PreparedMessage"][];
            /**
             * Review Required
             * @default true
             * @constant
             */
            review_required: true;
        };
        /** PendingReview */
        PendingReview: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "scope" | "cost" | "identity" | "fields" | "profile" | "draft";
            /** Revision */
            revision: number;
        };
        /** PersonDetailArguments */
        PersonDetailArguments: {
            /** Id */
            id: string;
        };
        /** PipelineReport */
        PipelineReport: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Scope */
            scope: string[];
            /** Rows */
            rows: components["schemas"]["PipelineRow"][];
            /** Unavailable Buyer Ids */
            unavailable_buyer_ids: string[];
            /** Methodology */
            methodology: string;
            /**
             * Filters
             * @default {}
             */
            filters: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Record Basis
             * @default []
             */
            record_basis: {
                [key: string]: components["schemas"]["JsonValue"];
            }[];
        };
        /** PipelineRow */
        PipelineRow: {
            buyer: components["schemas"]["NativeRef"];
            /** Stage */
            stage: string | null;
            /** Advisory Score */
            advisory_score: number | null;
            value: components["schemas"]["Money"] | null;
            /** Next Action */
            next_action: string | null;
        };
        /** PlanStep */
        PlanStep: {
            /** Section */
            section: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "model" | "review";
            /**
             * Max Input Tokens
             * @default 6000
             * @constant
             */
            max_input_tokens: 6000;
            /**
             * Max Output Tokens
             * @default 1000
             * @constant
             */
            max_output_tokens: 1000;
            /**
             * Deadline Seconds
             * @default 30
             * @constant
             */
            deadline_seconds: 30;
        };
        /** PreparedMessage */
        PreparedMessage: {
            /** Subject */
            subject: string;
            /** Body */
            body: string;
            /** Rationale */
            rationale: string;
            /** Evidence */
            evidence: components["schemas"]["SourceRef"][];
            /** Suggested Day */
            suggested_day: number;
        };
        /** ProfileProposal */
        ProfileProposal: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Criteria */
            criteria: components["schemas"]["Finding"][];
            /** Exclusions */
            exclusions: string[];
            /** Personas */
            personas: string[];
            /**
             * Approval Required
             * @default true
             * @constant
             */
            approval_required: true;
        };
        /** ProgressPayload */
        ProgressPayload: {
            /**
             * Step Id
             * Format: uuid
             */
            step_id: string;
            /** Completed Steps */
            completed_steps: number;
            /** Total Steps */
            total_steps: number;
        };
        /** ProjectArguments */
        ProjectArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /** Offer Description */
            offer_description: string;
            /**
             * Buyer Id
             * @default null
             */
            buyer_id: string | null;
            /**
             * Recipient Id
             * @default null
             */
            recipient_id: string | null;
        };
        /** ProjectSetup */
        ProjectSetup: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Offer */
            offer: string;
            /** Missing Fields */
            missing_fields: string[];
            /** Next Steps */
            next_steps: string[];
            /**
             * Setup Basis
             * @default null
             */
            setup_basis: {
                [key: string]: components["schemas"]["JsonValue"];
            } | null;
        };
        /** ProposalArguments */
        ProposalArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /** Pain Points */
            pain_points: string[];
            /** Terms */
            terms: components["schemas"]["CommercialTerms"][];
            /**
             * Case Study Refs
             * @default []
             */
            case_study_refs: components["schemas"]["SourceRef"][];
        };
        /** ProspectArguments */
        ProspectArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /** Objective */
            objective: string;
            bounds?: components["schemas"]["ExecutionBounds"];
        };
        /** QualificationArguments */
        QualificationArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /** Profile Version */
            profile_version: number;
            /**
             * Rubric
             * @default BANT_MEDDIC
             * @constant
             */
            rubric: "BANT_MEDDIC";
        };
        /** QualificationAssessment */
        QualificationAssessment: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Rubric
             * @constant
             */
            rubric: "BANT_MEDDIC";
            /** Dimensions */
            dimensions: components["schemas"]["AssessmentDimension"][];
            /**
             * Advisory
             * @default true
             * @constant
             */
            advisory: true;
            /** Next Questions */
            next_questions: string[];
        };
        /** QuickArguments */
        QuickArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * @default null
             */
            buyer_id: string | null;
            /**
             * Research Question
             * @default null
             */
            research_question: string | null;
            /**
             * Max Sources
             * @default 3
             */
            max_sources: number;
        } | {
            /** Format: uuid */
            buyer_id: string;
        } | {
            research_question: string;
        };
        /** QuoteApproval */
        QuoteApproval: {
            /**
             * Quote Id
             * Format: uuid
             */
            quote_id: string;
            /** Fingerprint */
            fingerprint: string;
        };
        /** QuoteRequest */
        QuoteRequest: {
            /**
             * Stage
             * @enum {string}
             */
            stage: "search" | "detail";
            /**
             * Buyer Id
             * @default null
             */
            buyer_id: string | null;
            /**
             * Connection Id
             * @default null
             */
            connection_id: string | null;
            /**
             * Query
             * @default null
             */
            query: string | null;
            /**
             * Target
             * @default null
             */
            target: ("company" | "people") | null;
            /**
             * Search Receipt Id
             * @default null
             */
            search_receipt_id: string | null;
            /**
             * Selected Ids
             * @default []
             */
            selected_ids: string[];
            /**
             * Include Email
             * @default false
             */
            include_email: boolean;
        } & ({
            /** @constant */
            stage: "search";
            /** Format: uuid */
            buyer_id: string;
            /** Format: uuid */
            connection_id: string;
            query: string;
            /** @enum {unknown} */
            target: "company" | "people";
            search_receipt_id?: null;
            selected_ids?: unknown[];
            /** @constant */
            include_email?: false;
        } | {
            /** @constant */
            stage: "detail";
            /** Format: uuid */
            search_receipt_id: string;
            selected_ids: string[];
            buyer_id?: null;
            connection_id?: null;
            query?: null;
            target?: null;
        });
        /** ReconciliationEvidence */
        ReconciliationEvidence: {
            /**
             * Provider Request Id
             * @default null
             */
            provider_request_id: string | null;
            /**
             * Authoritative Usage
             * @default null
             */
            authoritative_usage: number | null;
            /**
             * Evidence Ref
             * Format: uuid
             */
            evidence_ref: string;
            /**
             * Resolution
             * @enum {string}
             */
            resolution: "usage" | "non_dispatch" | "unknown";
            /** Expected Version */
            expected_version: number;
            /**
             * Tool Receipt Id
             * @default null
             */
            tool_receipt_id: string | null;
        };
        /** ReportArguments */
        ReportArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Buyer Ids */
            buyer_ids: string[];
            /**
             * List Id
             * @default null
             */
            list_id: string | null;
        };
        /** ReportExport */
        ReportExport: {
            /**
             * Output Id
             * Format: uuid
             */
            output_id: string;
            /** Output Revision */
            output_revision: number;
            export_ref: components["schemas"]["NativeRef"];
            /**
             * Media Type
             * @constant
             */
            media_type: "application/pdf";
        };
        /** ResearchArguments */
        ResearchArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /**
             * Buyer Id
             * @default null
             */
            buyer_id: string | null;
            /**
             * Research Question
             * @default null
             */
            research_question: string | null;
            /**
             * Max Sources
             * @default 12
             */
            max_sources: number;
        } | {
            /** Format: uuid */
            buyer_id: string;
        } | {
            research_question: string;
        };
        /** ResearchReport */
        ResearchReport: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            /** Opportunities */
            opportunities: string[];
            /** Concerns */
            concerns: string[];
        };
        /** ReviewArguments */
        ReviewArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
            /** Buyer Ids */
            buyer_ids: string[];
            /**
             * Profile Id
             * Format: uuid
             */
            profile_id: string;
            /** Profile Version */
            profile_version: number;
        };
        /** RevisionRequest */
        RevisionRequest: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** SalesModelRequest */
        SalesModelRequest: {
            /**
             * Section
             * @default summary
             */
            section: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /**
             * Step Id
             * Format: uuid
             */
            step_id: string;
            /** Skill Id */
            skill_id: string;
            /** @constant */
            skill_version: "1";
            context: components["schemas"]["ContextSnapshot"];
            /** Model Id */
            model_id: string;
            /** Route */
            route: string;
            /** Arguments */
            arguments: {
                [key: string]: components["schemas"]["JsonValue"];
            };
        } & ({
            /** @constant */
            skill_id: "sales-prospect";
            arguments: components["schemas"]["ProspectArguments"];
        } | {
            /** @constant */
            skill_id: "sales-research";
            arguments: components["schemas"]["ResearchArguments"];
        } | {
            /** @constant */
            skill_id: "sales-quick";
            arguments: components["schemas"]["QuickArguments"];
        } | {
            /** @constant */
            skill_id: "sales-qualify";
            arguments: components["schemas"]["QualificationArguments"];
        } | {
            /** @constant */
            skill_id: "sales-contacts";
            arguments: components["schemas"]["ContactsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-outreach";
            arguments: components["schemas"]["OutreachArguments"];
        } | {
            /** @constant */
            skill_id: "sales-followup";
            arguments: components["schemas"]["FollowupArguments"];
        } | {
            /** @constant */
            skill_id: "sales-prep";
            arguments: components["schemas"]["MeetingArguments"];
        } | {
            /** @constant */
            skill_id: "sales-proposal";
            arguments: components["schemas"]["ProposalArguments"];
        } | {
            /** @constant */
            skill_id: "sales-objections";
            arguments: components["schemas"]["ObjectionsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-icp";
            arguments: components["schemas"]["ICPArguments"];
        } | {
            /** @constant */
            skill_id: "sales-competitors";
            arguments: components["schemas"]["CompetitorsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-report";
            arguments: components["schemas"]["ReportArguments"];
        } | {
            /** @constant */
            skill_id: "sales-report-pdf";
            arguments: components["schemas"]["ExportArguments"];
        } | {
            /** @constant */
            skill_id: "first-project";
            arguments: components["schemas"]["ProjectArguments"];
        } | {
            /** @constant */
            skill_id: "understand-documents";
            arguments: components["schemas"]["DocumentsArguments"];
        } | {
            /** @constant */
            skill_id: "review-buyers";
            arguments: components["schemas"]["ReviewArguments"];
        });
        /** SalesModelResult */
        SalesModelResult: {
            /** Candidate */
            candidate: components["schemas"]["SalesSectionCandidate"] | components["schemas"]["ActionProposal"];
            usage: components["schemas"]["ModelUsage"];
            /** Provider Ref */
            provider_ref: string;
            /** Model Id */
            model_id: string;
            /** Prompt Version */
            prompt_version: string;
        };
        /** SalesProposal */
        SalesProposal: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Problem */
            problem: string;
            /** Solution */
            solution: string;
            /** Terms */
            terms: components["schemas"]["CommercialTerms"][];
            /** Assumptions */
            assumptions: string[];
            /** Proof Points */
            proof_points: components["schemas"]["Finding"][];
            /** Followup */
            followup: components["schemas"]["PreparedMessage"][];
            /**
             * Review Required
             * @default true
             * @constant
             */
            review_required: true;
        };
        /**
         * SalesSectionCandidate
         * @description A validated child, never acceptable to OutputSave as a complete output.
         */
        SalesSectionCandidate: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "profile_proposal" | "research_report" | "qualification_assessment" | "enrichment_proposal" | "competitive_document" | "outreach_preparation" | "followup_preparation" | "meeting_brief" | "sales_proposal" | "objection_playbook" | "pipeline_report" | "report_export" | "project_setup" | "document_understanding" | "buyer_review";
            /** Section */
            section: string;
            content: unknown;
            /** Citations */
            citations: components["schemas"]["SourceRef"][];
            /**
             * Complete
             * @constant
             */
            complete: false;
        } & ({
            /** @constant */
            kind: "profile_proposal";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_profile_proposal_summary"];
        } | {
            /** @constant */
            kind: "research_report";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_research_report_summary"];
        } | {
            /** @constant */
            kind: "research_report";
            /** @constant */
            section: "findings";
            content: components["schemas"]["Section_research_report_findings"];
        } | {
            /** @constant */
            kind: "qualification_assessment";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_qualification_assessment_summary"];
        } | {
            /** @constant */
            kind: "enrichment_proposal";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_enrichment_proposal_summary"];
        } | {
            /** @constant */
            kind: "competitive_document";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_competitive_document_summary"];
        } | {
            /** @constant */
            kind: "outreach_preparation";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_outreach_preparation_summary"];
        } | {
            /** @constant */
            kind: "outreach_preparation";
            /** @constant */
            section: "messages";
            content: components["schemas"]["Section_outreach_preparation_messages"];
        } | {
            /** @constant */
            kind: "followup_preparation";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_followup_preparation_summary"];
        } | {
            /** @constant */
            kind: "followup_preparation";
            /** @constant */
            section: "messages";
            content: components["schemas"]["Section_followup_preparation_messages"];
        } | {
            /** @constant */
            kind: "meeting_brief";
            /** @constant */
            section: "cheat_sheet";
            content: components["schemas"]["Section_meeting_brief_cheat_sheet"];
        } | {
            /** @constant */
            kind: "meeting_brief";
            /** @constant */
            section: "agenda";
            content: components["schemas"]["Section_meeting_brief_agenda"];
        } | {
            /** @constant */
            kind: "meeting_brief";
            /** @constant */
            section: "next_steps";
            content: components["schemas"]["Section_meeting_brief_next_steps"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            /** @constant */
            section: "problem";
            content: components["schemas"]["Section_sales_proposal_problem"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            /** @constant */
            section: "solution";
            content: components["schemas"]["Section_sales_proposal_solution"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            /** @constant */
            section: "terms";
            content: components["schemas"]["Section_sales_proposal_terms"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            /** @constant */
            section: "proof_points";
            content: components["schemas"]["Section_sales_proposal_proof_points"];
        } | {
            /** @constant */
            kind: "sales_proposal";
            /** @constant */
            section: "followup";
            content: components["schemas"]["Section_sales_proposal_followup"];
        } | {
            /** @constant */
            kind: "objection_playbook";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_objection_playbook_summary"];
        } | {
            /** @constant */
            kind: "objection_playbook";
            /** @constant */
            section: "responses";
            content: components["schemas"]["Section_objection_playbook_responses"];
        } | {
            /** @constant */
            kind: "pipeline_report";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_pipeline_report_summary"];
        } | {
            /** @constant */
            kind: "pipeline_report";
            /** @constant */
            section: "rows";
            content: components["schemas"]["Section_pipeline_report_rows"];
        } | {
            /** @constant */
            kind: "report_export";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_report_export_summary"];
        } | {
            /** @constant */
            kind: "project_setup";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_project_setup_summary"];
        } | {
            /** @constant */
            kind: "document_understanding";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_document_understanding_summary"];
        } | {
            /** @constant */
            kind: "buyer_review";
            /** @constant */
            section: "summary";
            content: components["schemas"]["Section_buyer_review_summary"];
        });
        /** Scope */
        Scope: {
            /**
             * Workspace Id
             * Format: uuid
             */
            workspace_id: string;
            /**
             * Project Id
             * Format: uuid
             */
            project_id: string;
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
        };
        /** SearchArguments */
        SearchArguments: {
            /** Query */
            query: string;
            /**
             * Page
             * @default 1
             */
            page: number;
            /**
             * Page Size
             * @default 5
             */
            page_size: number;
        };
        /** Section_buyer_review_summary */
        Section_buyer_review_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Assessments */
            assessments: components["schemas"]["Finding"][];
            /** Proposed Buyer Ids */
            proposed_buyer_ids: string[];
        };
        /** Section_competitive_document_summary */
        Section_competitive_document_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Competitors */
            competitors: components["schemas"]["Finding"][];
            /** Strengths */
            strengths: components["schemas"]["Finding"][];
            /** Gaps */
            gaps: components["schemas"]["Finding"][];
            /** Switching Costs */
            switching_costs: string[];
        };
        /** Section_document_understanding_summary */
        Section_document_understanding_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Document Ids */
            document_ids: string[];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            /**
             * Extraction Status
             * @enum {string}
             */
            extraction_status: "complete" | "partial" | "unavailable";
            /**
             * Extracted Passages
             * @default []
             */
            extracted_passages: string[];
            /**
             * Question
             * @default null
             */
            question: string | null;
        };
        /** Section_enrichment_proposal_summary */
        Section_enrichment_proposal_summary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /** Buyer Version */
            buyer_version: number;
            /**
             * Identity Match
             * @enum {string}
             */
            identity_match: "resolved" | "ambiguous" | "conflicting" | "unresolved";
            /** Fields */
            fields: components["schemas"]["FieldChoice"][];
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
        };
        /** Section_followup_preparation_messages */
        Section_followup_preparation_messages: {
            /** Messages */
            messages: components["schemas"]["PreparedMessage"][];
        };
        /** Section_followup_preparation_summary */
        Section_followup_preparation_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Scenario
             * @enum {string}
             */
            scenario: "post_meeting" | "post_demo" | "post_proposal" | "recovery" | "nurture";
            interaction_ref: components["schemas"]["SourceRef"];
        };
        /** Section_meeting_brief_agenda */
        Section_meeting_brief_agenda: {
            /** Agenda */
            agenda: components["schemas"]["AgendaItem"][];
        };
        /** Section_meeting_brief_cheat_sheet */
        Section_meeting_brief_cheat_sheet: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Cheat Sheet */
            cheat_sheet: string;
            /** Attendees */
            attendees: components["schemas"]["Finding"][];
            /** Talking Points */
            talking_points: string[];
            /** Discovery Questions */
            discovery_questions: string[];
        };
        /** Section_meeting_brief_next_steps */
        Section_meeting_brief_next_steps: {
            /** Next Steps */
            next_steps: string[];
        };
        /** Section_objection_playbook_responses */
        Section_objection_playbook_responses: {
            /** Responses */
            responses: components["schemas"]["ObjectionResponse"][];
        };
        /** Section_objection_playbook_summary */
        Section_objection_playbook_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
        };
        /** Section_outreach_preparation_messages */
        Section_outreach_preparation_messages: {
            /** Messages */
            messages: components["schemas"]["PreparedMessage"][];
        };
        /** Section_outreach_preparation_summary */
        Section_outreach_preparation_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Framework
             * @enum {string}
             */
            framework: "PAS" | "AIDA" | "BAB" | "direct";
        };
        /** Section_pipeline_report_rows */
        Section_pipeline_report_rows: {
            /** Rows */
            rows: components["schemas"]["PipelineRow"][];
        };
        /** Section_pipeline_report_summary */
        Section_pipeline_report_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Scope */
            scope: string[];
            /** Unavailable Buyer Ids */
            unavailable_buyer_ids: string[];
            /** Methodology */
            methodology: string;
        };
        /** Section_profile_proposal_summary */
        Section_profile_proposal_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Criteria */
            criteria: components["schemas"]["Finding"][];
            /** Exclusions */
            exclusions: string[];
            /** Personas */
            personas: string[];
        };
        /** Section_project_setup_summary */
        Section_project_setup_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Offer */
            offer: string;
            /** Missing Fields */
            missing_fields: string[];
            /** Next Steps */
            next_steps: string[];
        };
        /** Section_qualification_assessment_summary */
        Section_qualification_assessment_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /**
             * Rubric
             * @constant
             */
            rubric: "BANT_MEDDIC";
            /** Dimensions */
            dimensions: components["schemas"]["AssessmentDimension"][];
            /** Next Questions */
            next_questions: string[];
        };
        /** Section_report_export_summary */
        Section_report_export_summary: {
            /**
             * Output Id
             * Format: uuid
             */
            output_id: string;
            /** Output Revision */
            output_revision: number;
            export_ref: components["schemas"]["NativeRef"];
            /**
             * Media Type
             * @constant
             */
            media_type: "application/pdf";
        };
        /** Section_research_report_findings */
        Section_research_report_findings: {
            /** Findings */
            findings: components["schemas"]["Finding"][];
        };
        /** Section_research_report_summary */
        Section_research_report_summary: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Opportunities */
            opportunities: string[];
            /** Concerns */
            concerns: string[];
        };
        /** Section_sales_proposal_followup */
        Section_sales_proposal_followup: {
            /** Followup */
            followup: components["schemas"]["PreparedMessage"][];
        };
        /** Section_sales_proposal_problem */
        Section_sales_proposal_problem: {
            /** Summary */
            summary: string;
            /** Unknowns */
            unknowns: string[];
            /** Problem */
            problem: string;
            /** Assumptions */
            assumptions: string[];
        };
        /** Section_sales_proposal_proof_points */
        Section_sales_proposal_proof_points: {
            /** Proof Points */
            proof_points: components["schemas"]["Finding"][];
        };
        /** Section_sales_proposal_solution */
        Section_sales_proposal_solution: {
            /** Solution */
            solution: string;
        };
        /** Section_sales_proposal_terms */
        Section_sales_proposal_terms: {
            /** Terms */
            terms: components["schemas"]["CommercialTerms"][];
        };
        /** SkillArguments */
        SkillArguments: {
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "zh-HK";
        };
        /** SkillDefinition */
        SkillDefinition: {
            /** Id */
            id: string;
            /**
             * Version
             * @constant
             */
            version: "1";
            /** Inputs Schema */
            inputs_schema: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Output Kind
             * @enum {string}
             */
            output_kind: "profile_proposal" | "research_report" | "qualification_assessment" | "enrichment_proposal" | "competitive_document" | "outreach_preparation" | "followup_preparation" | "meeting_brief" | "sales_proposal" | "objection_playbook" | "pipeline_report" | "report_export" | "project_setup" | "document_understanding" | "buyer_review";
            /** Allowed Actions */
            allowed_actions: ("search_company_xverum" | "search_people_xverum" | "enrich_company_xverum" | "enrich_person_xverum" | "get_email_xverum" | "research.read" | "profile.propose" | "buyers.review" | "lists.propose" | "drafts.prepare" | "documents.read" | "documents.prepare" | "reports.read" | "reports.export" | "tasks.plan")[];
            /**
             * Languages
             * @default [
             *       "en",
             *       "zh-HK"
             *     ]
             */
            languages: [
                "en",
                "zh-HK"
            ];
            /**
             * Budget Class
             * @enum {string}
             */
            budget_class: "model" | "model_and_provider_credits" | "export" | "bounded_orchestration";
            /** Upstream Hash */
            upstream_hash: string | null;
        };
        /** SkillPage */
        SkillPage: {
            /** Skills */
            skills: components["schemas"]["SkillDefinition"][];
        };
        /** SkillPageResponse */
        SkillPageResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["SkillPage"];
        };
        /** SourceRef */
        SourceRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Version */
            version: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "project_fact" | "profile" | "buyer" | "document" | "output" | "run" | "provider_evidence" | "drive";
            /** Locator */
            locator: string;
            /**
             * Retention Class
             * @enum {string}
             */
            retention_class: "durable" | "metadata_only" | "zero_content";
        };
        /** StatePayload */
        StatePayload: {
            /**
             * State
             * @enum {string}
             */
            state: "needs_input" | "ready_for_review" | "queued" | "running" | "partially_completed" | "completed" | "failed" | "cancel_requested" | "cancelled" | "outcome_unknown";
            /** Revision */
            revision: number;
        };
        /** StepAdmission */
        StepAdmission: {
            proposal: components["schemas"]["ActionProposal"];
            /**
             * Review Id
             * Format: uuid
             */
            review_id: string;
        };
        /** StepCollection */
        StepCollection: {
            /** Items */
            items: components["schemas"]["StepReceipt"][];
        };
        /** StepCollectionResponse */
        StepCollectionResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["StepCollection"];
        };
        /** StepReceipt */
        StepReceipt: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Task Id */
            task_id: string | null;
            /**
             * Dispatch State
             * @enum {string}
             */
            dispatch_state: "queued" | "submitting" | "received" | "failed" | "cancelled" | "unknown";
            /** Native Operation Id */
            native_operation_id: string | null;
            /** Reservation Ids */
            reservation_ids: string[];
        };
        /** StepReceiptResponse */
        StepReceiptResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["StepReceipt"];
        };
        /** StepReviewInput */
        StepReviewInput: {
            proposal: components["schemas"]["ActionProposal"];
            /** Fingerprint */
            fingerprint: string;
        };
        /** TaskCollectionPage */
        TaskCollectionPage: {
            /** Items */
            items: components["schemas"]["TaskDetail"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /** TaskCollectionResponse */
        TaskCollectionResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["TaskCollectionPage"];
        };
        /** TaskDetail */
        TaskDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * State
             * @enum {string}
             */
            state: "needs_input" | "ready_for_review" | "queued" | "running" | "partially_completed" | "completed" | "failed" | "cancel_requested" | "cancelled" | "outcome_unknown";
            /** Revision */
            revision: number;
            /** Context Digest */
            context_digest: string | null;
            /** Output Ids */
            output_ids: string[];
            pending_review: components["schemas"]["PendingReview"] | null;
            /**
             * Thread Id
             * Format: uuid
             */
            thread_id: string;
            /** Skill Id */
            skill_id: string;
            /** Skill Version */
            skill_version: string;
            /** Message Sequence */
            message_sequence: number;
            /** Intake */
            intake: components["schemas"]["IntakeEntry"][];
            /** Arguments */
            arguments: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
            /** Missing Inputs */
            missing_inputs: string[];
        };
        /** TaskDetailResponse */
        TaskDetailResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["TaskDetail"];
        };
        /** TaskEvent */
        TaskEvent: {
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
            /** Sequence */
            sequence: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "progress" | "state" | "output" | "review" | "error";
            /** Payload */
            payload: components["schemas"]["ProgressPayload"] | components["schemas"]["StatePayload"] | components["schemas"]["OutputPayload"] | components["schemas"]["PendingReview"] | components["schemas"]["ErrorPayload"];
        } & ({
            /** @constant */
            kind: "progress";
            payload: components["schemas"]["ProgressPayload"];
        } | {
            /** @constant */
            kind: "state";
            payload: components["schemas"]["StatePayload"];
        } | {
            /** @constant */
            kind: "output";
            payload: components["schemas"]["OutputPayload"];
        } | {
            /** @constant */
            kind: "review";
            payload: components["schemas"]["PendingReview"];
        } | {
            /** @constant */
            kind: "error";
            payload: components["schemas"]["ErrorPayload"];
        });
        /** TaskFollowup */
        TaskFollowup: {
            /** User Message */
            user_message: string;
            /** Arguments */
            arguments: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Source Refs */
            source_refs?: components["schemas"]["SourceRef"][] | null;
        };
        /** TaskInput */
        TaskInput: {
            /**
             * Thread Id
             * Format: uuid
             */
            thread_id: string;
            /** Skill Id */
            skill_id: string;
            /** @constant */
            skill_version: "1";
            /** User Message */
            user_message: string;
            /** Source Refs */
            source_refs: components["schemas"]["SourceRef"][];
            arguments: unknown;
        } & ({
            /** @constant */
            skill_id: "sales-prospect";
            arguments: components["schemas"]["IntakeProspectArguments"];
        } | {
            /** @constant */
            skill_id: "sales-research";
            arguments: components["schemas"]["IntakeResearchArguments"];
        } | {
            /** @constant */
            skill_id: "sales-quick";
            arguments: components["schemas"]["IntakeQuickArguments"];
        } | {
            /** @constant */
            skill_id: "sales-qualify";
            arguments: components["schemas"]["IntakeQualificationArguments"];
        } | {
            /** @constant */
            skill_id: "sales-contacts";
            arguments: components["schemas"]["IntakeContactsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-outreach";
            arguments: components["schemas"]["IntakeOutreachArguments"];
        } | {
            /** @constant */
            skill_id: "sales-followup";
            arguments: components["schemas"]["IntakeFollowupArguments"];
        } | {
            /** @constant */
            skill_id: "sales-prep";
            arguments: components["schemas"]["IntakeMeetingArguments"];
        } | {
            /** @constant */
            skill_id: "sales-proposal";
            arguments: components["schemas"]["IntakeProposalArguments"];
        } | {
            /** @constant */
            skill_id: "sales-objections";
            arguments: components["schemas"]["IntakeObjectionsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-icp";
            arguments: components["schemas"]["IntakeICPArguments"];
        } | {
            /** @constant */
            skill_id: "sales-competitors";
            arguments: components["schemas"]["IntakeCompetitorsArguments"];
        } | {
            /** @constant */
            skill_id: "sales-report";
            arguments: components["schemas"]["IntakeReportArguments"];
        } | {
            /** @constant */
            skill_id: "sales-report-pdf";
            arguments: components["schemas"]["IntakeExportArguments"];
        } | {
            /** @constant */
            skill_id: "first-project";
            arguments: components["schemas"]["IntakeProjectArguments"];
        } | {
            /** @constant */
            skill_id: "understand-documents";
            arguments: components["schemas"]["IntakeDocumentsArguments"];
        } | {
            /** @constant */
            skill_id: "review-buyers";
            arguments: components["schemas"]["IntakeReviewArguments"];
        });
        /**
         * TaskMutationHeaders
         * @description Selected native headers; create targets thread version, cancel task revision.
         */
        TaskMutationHeaders: {
            /** Idempotency-Key */
            "Idempotency-Key": string;
            /** If-Match */
            "If-Match": string;
        };
        /** TaskPlan */
        TaskPlan: {
            /** Steps */
            steps: components["schemas"]["PlanStep"][];
            /** Missing Inputs */
            missing_inputs: string[];
            /**
             * Output Kind
             * @enum {string}
             */
            output_kind: "profile_proposal" | "research_report" | "qualification_assessment" | "enrichment_proposal" | "competitive_document" | "outreach_preparation" | "followup_preparation" | "meeting_brief" | "sales_proposal" | "objection_playbook" | "pipeline_report" | "report_export" | "project_setup" | "document_understanding" | "buyer_review";
            bounds?: components["schemas"]["ExecutionBounds"];
            /**
             * Input Token Budget
             * @default 0
             */
            input_token_budget: number;
            /**
             * Output Token Budget
             * @default 0
             */
            output_token_budget: number;
        };
        /** TaskRecord */
        TaskRecord: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * State
             * @enum {string}
             */
            state: "needs_input" | "ready_for_review" | "queued" | "running" | "partially_completed" | "completed" | "failed" | "cancel_requested" | "cancelled" | "outcome_unknown";
            /** Revision */
            revision: number;
            /** Context Digest */
            context_digest: string | null;
            /** Output Ids */
            output_ids: string[];
            pending_review: components["schemas"]["PendingReview"] | null;
        } & unknown;
        /** TaskRecordResponse */
        TaskRecordResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["TaskRecord"];
        };
        /** ToolPlanItem */
        ToolPlanItem: {
            /**
             * Tool
             * @enum {string}
             */
            tool: "search_company_xverum" | "search_people_xverum" | "enrich_company_xverum" | "enrich_person_xverum" | "get_email_xverum";
            /** Arguments */
            arguments: components["schemas"]["SearchArguments"] | components["schemas"]["CompanyDetailArguments"] | components["schemas"]["PersonDetailArguments"];
        } & ({
            /** @constant */
            tool: "search_company_xverum";
            arguments: components["schemas"]["SearchArguments"];
        } | {
            /** @constant */
            tool: "search_people_xverum";
            arguments: components["schemas"]["SearchArguments"];
        } | {
            /** @constant */
            tool: "enrich_company_xverum";
            arguments: components["schemas"]["CompanyDetailArguments"];
        } | {
            /** @constant */
            tool: "enrich_person_xverum";
            arguments: components["schemas"]["PersonDetailArguments"];
        } | {
            /** @constant */
            tool: "get_email_xverum";
            arguments: components["schemas"]["PersonDetailArguments"];
        });
        /** XverumBusinessEmail */
        XverumBusinessEmail: {
            /** Has Email */
            has_email: boolean;
            /** Emails */
            emails: components["schemas"]["XverumEmail"][];
        };
        /** XverumCompanyCard */
        XverumCompanyCard: {
            /** Social Url */
            social_url: string | null;
            /** Company Name */
            company_name: string | null;
            /** Slogan */
            slogan: string | null;
            /** Headquarters */
            headquarters: string | null;
            /** Country Code */
            country_code: string | null;
            /** Industry */
            industry: string | null;
            /** Employees Num */
            employees_num: number | null;
            /** Website */
            website: string | null;
            /** Founded */
            founded: number | null;
            /** Id */
            id: string;
        };
        /** XverumCompanyDetail */
        XverumCompanyDetail: {
            /** Social Url */
            social_url: string | null;
            /** Company Name */
            company_name: string | null;
            /** Slogan */
            slogan: string | null;
            /** Headquarters */
            headquarters: string | null;
            /** Country Code */
            country_code: string | null;
            /** Industry */
            industry: string | null;
            /** Employees Num */
            employees_num: number | null;
            /** Website */
            website: string | null;
            /** Founded */
            founded: number | null;
            /** About Us */
            about_us: string | null;
            /** Specialties */
            specialties: string[];
            /** Locations */
            locations: components["schemas"]["XverumLocation"][];
            /** Type */
            type: string | null;
            /** Social Followers */
            social_followers: number | null;
        };
        /** XverumCompanyFields */
        XverumCompanyFields: {
            /** Social Url */
            social_url: string | null;
            /** Company Name */
            company_name: string | null;
            /** Slogan */
            slogan: string | null;
            /** Headquarters */
            headquarters: string | null;
            /** Country Code */
            country_code: string | null;
            /** Industry */
            industry: string | null;
            /** Employees Num */
            employees_num: number | null;
            /** Website */
            website: string | null;
            /** Founded */
            founded: number | null;
        };
        /** XverumCompanySearch */
        XverumCompanySearch: {
            /**
             * Result Type
             * @constant
             */
            result_type: "company";
            /** Results */
            results: components["schemas"]["XverumCompanyCard"][];
            /** Total Count */
            total_count: number;
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
        };
        /** XverumEmail */
        XverumEmail: {
            /** Email */
            email: string;
            /** Confidence */
            confidence: string | null;
            /** Last Checked */
            last_checked: string | null;
        };
        /**
         * XverumExperience
         * @description Minimal employer/role chronology; no personal-background narratives.
         */
        XverumExperience: {
            /** Position */
            position: string | null;
            /** Company Name */
            company_name: string | null;
            /** Start Time */
            start_time: string | null;
            /** End Time */
            end_time: string | null;
        };
        /** XverumLiability */
        XverumLiability: {
            receipt: components["schemas"]["XverumReceipt"];
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
            /** Connection Generation */
            connection_generation: number;
            /** Account Ref */
            account_ref: string;
            /** Tools */
            tools: components["schemas"]["XverumToolLiability"][];
        };
        /** XverumLiabilityResponse */
        XverumLiabilityResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["XverumLiability"];
        };
        /** XverumLocation */
        XverumLocation: {
            /**
             * Address
             * @default null
             */
            address: string | null;
            /**
             * Address 2
             * @default null
             */
            address_2: string | null;
            /**
             * Primary
             * @default null
             */
            primary: boolean | null;
        };
        /** XverumPeopleSearch */
        XverumPeopleSearch: {
            /**
             * Result Type
             * @constant
             */
            result_type: "people";
            /** Results */
            results: components["schemas"]["XverumPersonCard"][];
            /** Total Count */
            total_count: number;
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
        };
        /** XverumPersonCard */
        XverumPersonCard: {
            /** Id */
            id: string;
            /** Full Name */
            full_name: string;
            /** Social Url */
            social_url: string | null;
            /** Headline */
            headline: string | null;
            /** Location */
            location: string | null;
            /** Company Name */
            company_name: string | null;
            /** Position */
            position: string | null;
            /** Industry */
            industry: string | null;
            /** Evidence Summary */
            evidence_summary: string;
        };
        /** XverumPersonDetail */
        XverumPersonDetail: {
            /** Full Name */
            full_name: string;
            /** Social Url */
            social_url: string | null;
            /** Headline */
            headline: string | null;
            /** Location */
            location: string | null;
            /** Company Name */
            company_name: string | null;
            /** Position */
            position: string | null;
            /** Industry */
            industry: string | null;
            /** Evidence Summary */
            evidence_summary: string;
            /** Experience */
            experience: components["schemas"]["XverumExperience"][];
            /** Seniority */
            seniority: string | null;
        };
        /** XverumQuote */
        XverumQuote: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Stage
             * @enum {string}
             */
            stage: "search" | "detail";
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Connection Generation */
            connection_generation: number;
            /** Query */
            query: string | null;
            /** Provider Ids */
            provider_ids: string[];
            /** Tool Plan */
            tool_plan: components["schemas"]["ToolPlanItem"][];
            /** Max Credits */
            max_credits: number;
            /** Tariff Version */
            tariff_version: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Fingerprint */
            fingerprint: string;
            /**
             * Buyer Id
             * Format: uuid
             */
            buyer_id: string;
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
        };
        /** XverumQuoteResponse */
        XverumQuoteResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["XverumQuote"];
        };
        /** XverumReceipt */
        XverumReceipt: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Version
             * @default 1
             */
            version: number;
            /**
             * Dispatch State
             * @enum {string}
             */
            dispatch_state: "reserved" | "dispatched" | "settled" | "outcome_unknown" | "cancelled";
            /** Request Id */
            request_id: string | null;
            /** Credits Used */
            credits_used: number | null;
            /** Held Credits */
            held_credits: number;
            /** Projection Digest */
            projection_digest: string | null;
        };
        /** XverumReceiptResponse */
        XverumReceiptResponse: {
            /** Request Id */
            request_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "live";
            data: components["schemas"]["XverumReceipt"];
        };
        /** XverumResult */
        XverumResult: {
            /**
             * Tool
             * @enum {string}
             */
            tool: "search_company_xverum" | "search_people_xverum" | "enrich_company_xverum" | "enrich_person_xverum" | "get_email_xverum";
            /** Request Id */
            request_id: string;
            /** Credits Used */
            credits_used: number;
            /** Credits Remaining */
            credits_remaining: number;
            /** Projection */
            projection: components["schemas"]["XverumPeopleSearch"] | components["schemas"]["XverumCompanySearch"] | components["schemas"]["XverumPersonDetail"] | components["schemas"]["XverumCompanyDetail"] | components["schemas"]["XverumBusinessEmail"];
        } & ({
            /** @constant */
            tool: "search_company_xverum";
            projection: components["schemas"]["XverumCompanySearch"];
        } | {
            /** @constant */
            tool: "search_people_xverum";
            projection: components["schemas"]["XverumPeopleSearch"];
        } | {
            /** @constant */
            tool: "enrich_company_xverum";
            projection: components["schemas"]["XverumCompanyDetail"];
        } | {
            /** @constant */
            tool: "enrich_person_xverum";
            projection: components["schemas"]["XverumPersonDetail"];
        } | {
            /** @constant */
            tool: "get_email_xverum";
            projection: components["schemas"]["XverumBusinessEmail"];
        });
        /** XverumToolLiability */
        XverumToolLiability: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ordinal */
            ordinal: number;
            /**
             * Tool
             * @enum {string}
             */
            tool: "search_company_xverum" | "search_people_xverum" | "enrich_company_xverum" | "enrich_person_xverum" | "get_email_xverum";
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "submitting" | "unknown" | "received" | "nonaccepted" | "cancelled";
            /** Request Id */
            request_id: string | null;
            /** Credits Used */
            credits_used: number | null;
        };
        XverumCandidatesResponse: {
            request_id: string;
            /** @constant */
            data_mode: "live";
            data: components["schemas"]["XverumCandidates"];
        };
        XverumCandidates: components["schemas"]["XverumCompanySearch"] | components["schemas"]["XverumPeopleSearch"];
        OutputPermissions: {
            can_edit: boolean;
        };
        OutputPermissionsResponse: {
            request_id: string;
            /** @constant */
            data_mode: "live";
            data: components["schemas"]["OutputPermissions"];
        };
        XverumTaskStage: {
            receipt: components["schemas"]["XverumReceipt"];
            /** @enum {string} */
            stage: "search" | "detail";
            /** Format: uuid */
            search_receipt_id: string | null;
            selected_ids?: string[];
            reviewed_ids?: string[];
            previous_proposal_id?: string | null;
        };
        XverumTaskStages: {
            items: components["schemas"]["XverumTaskStage"][];
        };
        XverumTaskStagesResponse: {
            request_id: string;
            /** @constant */
            data_mode: "live";
            data: components["schemas"]["XverumTaskStages"];
        };
        /** SalesCapability */
        SalesCapability: {
            /** Admission Enabled */
            admission_enabled: boolean;
        };
        /** SalesNativeSources */
        SalesNativeSources: {
            /** Items */
            items: components["schemas"]["SalesNativeSource"][];
        };
        /** SalesNativeSource */
        SalesNativeSource: {
            /** Label */
            label: string;
            ref: components["schemas"]["SourceRef"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listSalesSkills: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillPageResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesTasks: {
        parameters: {
            query: {
                thread_id: string;
                offset?: number;
                limit?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskCollectionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createSalesTask: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current thread version from TaskInput.thread_id. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskInput"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            201: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskDetailResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesTask: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskDetailResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesTaskEvents: {
        parameters: {
            query?: {
                /** @description Replay events with sequence strictly greater than after; omitted means zero. Never dispatches work. */
                after?: number;
                limit?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EventPageResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    cancelSalesTask: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current task revision. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskRecordResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesOutputs: {
        parameters: {
            query?: {
                /** @description Supply native_surface and native_id together to filter by a canonical native record; omit both for the accessible project collection. */
                native_surface?: "profile" | "buyer" | "list" | "run" | "draft" | "document" | "export";
                /** @description Supply native_surface and native_id together to filter by a canonical native record; omit both for the accessible project collection. */
                native_id?: string;
                /** @description Bounded ACL-filtered collection pagination. */
                offset?: number;
                /** @description Bounded ACL-filtered collection pagination. */
                limit?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputCollectionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveSalesOutput: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OutputSave"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputVersionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesOutputRevision: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputVersionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesOutputVersions: {
        parameters: {
            query?: {
                before_revision?: number;
                limit?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputPageResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    regenerateSalesOutput: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current thread version from TaskInput.thread_id. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskInput"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskRecordResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    exportSalesReport: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportArguments"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputVersionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listXverumConnections: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionPageResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    assignXverumConnection: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionAssignment"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong connection.version ETag */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionBindingResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disconnectXverumConnection: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong connection.version ETag */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionBindingResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createXverumQuote: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuoteRequest"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumQuoteResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getXverumQuote: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                quote_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumQuoteResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveXverumQuote: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                quote_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuoteApproval"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getXverumReceipt: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong current receipt.version ETag for subsequent operator reconciliation. */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesOutput: {
        parameters: {
            query?: {
                /** @description Exact revision when supplied; otherwise latest canonical revision. Never fall back to an older revision if the requested/latest content is unavailable. */
                revision?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputVersionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    followupSalesTask: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current task revision. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskFollowup"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskDetailResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveSalesStep: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current task revision. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepReviewInput"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionReviewResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesSteps: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepCollectionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    admitSalesStep: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current task revision. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepAdmission"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewSalesExecution: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActionProposal"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionPreviewResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    applySalesNativeAction: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required strong ETag of the selected native target revision, for example "2". Exact successful retries retain their original precondition. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActionProposal"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NativeRefResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The selected native target revision is stale (STALE_REVISION). No mutation is applied. */
            412: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewSalesOutput: {
        parameters: {
            query?: {
                /** @description Exact revision when supplied; otherwise latest canonical revision. Never fall back to an older revision if the requested/latest content is unavailable. */
                revision?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    "Content-Security-Policy": "default-src 'none'; sandbox";
                    "Referrer-Policy": "no-referrer";
                    "X-Content-Type-Options": "nosniff";
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reviewSalesOutput: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputReviewResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    rotateXverumConnection: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Strong current connection.version ETag, independent of expected_generation in the body. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionRotation"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong connection.version ETag */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionBindingResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reconcileXverumReceipt: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReconciliationEvidence"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong current receipt.version ETag for subsequent operator reconciliation. */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    cancelXverumReceipt: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong current receipt.version ETag for subsequent operator reconciliation. */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getXverumLiability: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong current receipt.version ETag for subsequent operator reconciliation. */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumLiabilityResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveLinkedXverumQuote: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                quote_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuoteApproval"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepReceiptResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getEnrichmentProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnrichmentProposalResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    applyEnrichmentProposal: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnrichmentApply"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NativeRefResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createEnrichmentProposal: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnrichmentCreate"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnrichmentProposalResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesCoreGuidance: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CoreGuidanceResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    prepareSalesCoreOutput: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required current task revision. Strong quoted integer ETag, e.g. "4". Missing/malformed: 400 INVALID_REQUEST; stale: 409 STALE_REVISION. Included in idempotency identity. Direct API header; native hosting transport may carry X-BuyerOS-If-Match and restore it before validation; never send both. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputVersionResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createSalesFormalDraft: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required strong ETag of the selected native target revision, for example "2". Exact successful retries retain their original precondition. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FormalDraftInput"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NativeRefResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The selected native target revision is stale (STALE_REVISION). No mutation is applied. */
            412: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    exportSalesOutput: {
        parameters: {
            query?: never;
            header: {
                /** @description Native opaque 8..200-character key, bound to actor, operation, target, body and If-Match; different intent with the same key conflicts. */
                "Idempotency-Key": string;
                /** @description Required strong ETag of the selected native target revision, for example "2". Exact successful retries retain their original precondition. */
                "If-Match": string;
            };
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OutputExportInput"];
            };
        };
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NativeRefResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The selected native target revision is stale (STALE_REVISION). No mutation is applied. */
            412: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getXverumCandidates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Strong current receipt.version ETag for subsequent operator reconciliation. */
                    ETag: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumCandidatesResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesOutputPermissions: {
        parameters: {
            query?: {
                /** @description Exact revision when supplied; otherwise latest canonical revision. Never fall back to an older revision if the requested/latest content is unavailable. */
                revision?: number;
            };
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                output_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutputPermissionsResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listXverumTaskStages: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["XverumTaskStagesResponse"];
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSalesCapability: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SalesCapability"];
                        /** @enum {string} */
                        data_mode: "live";
                        request_id: string;
                    };
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSalesNativeSources: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                workspace_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Native live envelope containing canonical validated readback. */
            200: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SalesNativeSources"];
                        /** @enum {string} */
                        data_mode: "live";
                        request_id: string;
                    };
                };
            };
            /** @description INVALID_REQUEST: missing/malformed native request headers or preconditions. */
            400: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden operation; inaccessible resources remain 404. */
            403: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unavailable or inaccessible resource */
            404: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description STALE_REVISION or IDEMPOTENCY_CONFLICT; do not silently retry with a different precondition. */
            409: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid contract */
            422: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description RATE_LIMITED; observe Retry-After when present. */
            429: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    /** @description Native RATE_LIMITED handler emits 60 seconds. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description INTERNAL_ERROR; no internals exposed. */
            500: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Configuration required or capability unavailable */
            503: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Other non-2xx responses use the same native error body; never FastAPI detail or a live success envelope. */
            default: {
                headers: {
                    /** @description no-store on successful and error responses, including replay, validation and permission failures. */
                    "Cache-Control": "no-store";
                    /** @description Native request correlation ID; matches the body request_id. */
                    "X-Request-ID": string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
