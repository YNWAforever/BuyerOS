// Generated from API-owned internal5 OpenAPI; do not edit.
export interface paths {
    "/v1/internal/worker/claim": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Claim */
        post: operations["workerClaim"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/internal/worker/maintenance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Maintenance */
        post: operations["workerMaintenance"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/internal/worker/publication": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publication */
        post: operations["workerRecordPublication"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/internal/worker/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Status */
        post: operations["workerStepStatus"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/internal/worker/step": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Step */
        post: operations["workerExecuteStep"];
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
        /** ClaimBatch */
        ClaimBatch: {
            /** Items */
            items: components["schemas"]["JobEnvelope"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Runtime Epoch */
            runtime_epoch: number;
        };
        /** ClaimRequest */
        ClaimRequest: {
            /**
             * Max Total
             * @default 10
             */
            max_total: number;
            /** Runtime Epoch */
            runtime_epoch: number;
            /**
             * Time Budget Seconds
             * @default 10
             */
            time_budget_seconds: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** JobEnvelope */
        JobEnvelope: {
            /** Generation */
            generation: number;
            /**
             * Outbox Id
             * Format: uuid
             */
            outbox_id: string;
            /** Runtime Epoch */
            runtime_epoch: number;
            /**
             * V
             * @constant
             */
            v: 1;
            /**
             * Workspace Id
             * Format: uuid
             */
            workspace_id: string;
        };
        /** MaintenanceRequest */
        MaintenanceRequest: {
            /** Runtime Epoch */
            runtime_epoch: number;
        };
        /** MaintenanceResult */
        MaintenanceResult: {
            /** Enabled */
            enabled: boolean;
            /** Recovered */
            recovered: number;
            /** Runtime Epoch */
            runtime_epoch: number;
        };
        /** PublicationRequest */
        PublicationRequest: {
            envelope: components["schemas"]["JobEnvelope"];
            /**
             * State
             * @enum {string}
             */
            state: "published" | "unknown" | "failed";
        };
        /** StepOutcome */
        StepOutcome: {
            /**
             * Code
             * @enum {string}
             */
            code: "OK" | "EXECUTION_DISABLED" | "CAPABILITY_UNAVAILABLE" | "POLICY_CHANGED" | "ACTOR_CHANGED" | "INVALID_INTENT" | "STALE_FENCE" | "IN_PROGRESS" | "TRANSIENT_UNAVAILABLE" | "PROVIDER_UNKNOWN" | "LIMIT_EXCEEDED" | "STEP_FAILED";
            /** Next Step Key */
            next_step_key: string | null;
            /** Retry At */
            retry_at: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "done" | "continue" | "retry_later" | "reconcile" | "blocked" | "stale";
        };
        /** StepRequest */
        StepRequest: {
            envelope: components["schemas"]["JobEnvelope"];
            /** Step Key */
            step_key: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
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
    workerClaim: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClaimRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClaimBatch"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    workerMaintenance: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaintenanceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaintenanceResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    workerRecordPublication: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepOutcome"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    workerStepStatus: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepOutcome"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    workerExecuteStep: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepOutcome"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
