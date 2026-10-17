"""Controlled manual policy requests; frozen additive schema, no activation rows."""
from alembic import op
import sqlalchemy as sa

revision = "0056_policy_activation"
down_revision = "0055_lead_workflow"
branch_labels = depends_on = None
TABLES = ("policy_controller_authorities", "policy_activation_requests", "policy_activation_resolutions")
FROZEN_DDL = ("\nCREATE TABLE policy_controller_authorities (\n\tproject_id UUID NOT NULL, \n\tapprover_user_id UUID NOT NULL, \n\tmembership_version INTEGER NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tpurposes VARCHAR(32)[] NOT NULL, \n\tallowed_actions VARCHAR(64)[] NOT NULL, \n\tvalid_from TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdesignation_reference VARCHAR(1000) NOT NULL, \n\tdesignation_sha256 VARCHAR(64) NOT NULL, \n\tmanifest_sha256 VARCHAR(64) NOT NULL, \n\texecution_receipt JSONB NOT NULL, \n\tsupersedes_id UUID, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_policy_controller_authorities PRIMARY KEY (id), \n\tCONSTRAINT uq_policy_authority_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_policy_authority_binding UNIQUE (workspace_id, project_id, id, version), \n\tCONSTRAINT uq_policy_authority_version UNIQUE (workspace_id, project_id, approver_user_id, version), \n\tCONSTRAINT uq_policy_authority_manifest UNIQUE (workspace_id, manifest_sha256), \n\tCONSTRAINT fk_pauthority_project FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_pauthority_member FOREIGN KEY(workspace_id, approver_user_id) REFERENCES memberships (workspace_id, user_id), \n\tCONSTRAINT fk_pauthority_previous FOREIGN KEY(workspace_id, supersedes_id) REFERENCES policy_controller_authorities (workspace_id, id), \n\tCONSTRAINT ck_policy_controller_authorities_policy_authority_versions CHECK (version>=1 AND membership_version>=1), \n\tCONSTRAINT ck_policy_controller_authorities_policy_authority_state CHECK (status IN ('active','revoked') AND valid_from<expires_at), \n\tCONSTRAINT ck_policy_controller_authorities_policy_authority_purposes CHECK (cardinality(purposes) BETWEEN 1 AND 4 AND purposes <@ ARRAY['account_research','contact_research','draft_preparation','outreach']::varchar[])\n)\n\n", 'CREATE INDEX ix_policy_authority_current ON policy_controller_authorities (workspace_id, project_id, approver_user_id, version)', 'CREATE INDEX ix_policy_controller_authorities_workspace_id ON policy_controller_authorities (workspace_id)', "\nCREATE TABLE policy_activation_requests (\n\tproject_id UUID NOT NULL, \n\trequester_id UUID NOT NULL, \n\tclient_request_id UUID NOT NULL, \n\tauthority_id UUID NOT NULL, \n\tauthority_version INTEGER NOT NULL, \n\texpected_policy_id UUID, \n\texpected_policy_version INTEGER, \n\tterms JSONB NOT NULL, \n\tterms_hash VARCHAR(64) NOT NULL, \n\trequest_deadline TIMESTAMP WITH TIME ZONE NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_policy_activation_requests PRIMARY KEY (id), \n\tCONSTRAINT uq_policy_request_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_policy_request_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT uq_policy_request_client UNIQUE (workspace_id, requester_id, client_request_id), \n\tCONSTRAINT fk_prequest_project FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_prequest_member FOREIGN KEY(workspace_id, requester_id) REFERENCES memberships (workspace_id, user_id), \n\tCONSTRAINT fk_prequest_authority FOREIGN KEY(workspace_id, project_id, authority_id, authority_version) REFERENCES policy_controller_authorities (workspace_id, project_id, id, version), \n\tCONSTRAINT fk_prequest_previous FOREIGN KEY(workspace_id, expected_policy_id) REFERENCES policy_decisions (workspace_id, id), \n\tCONSTRAINT ck_policy_activation_requests_policy_request_prior_pair CHECK ((expected_policy_id IS NULL)=(expected_policy_version IS NULL)), \n\tCONSTRAINT ck_policy_activation_requests_policy_request_terms_scope CHECK (jsonb_typeof(terms)='object' AND terms->>'workspace_id'=workspace_id::text AND terms->>'controller_scope_id'=workspace_id::text AND terms->>'project_id'=project_id::text)\n)\n\n", 'CREATE INDEX ix_policy_activation_requests_workspace_id ON policy_activation_requests (workspace_id)', 'CREATE INDEX ix_policy_request_project ON policy_activation_requests (workspace_id, project_id, created_at)', "\nCREATE TABLE policy_activation_resolutions (\n\tproject_id UUID NOT NULL, \n\trequest_id UUID NOT NULL, \n\tactor_id UUID NOT NULL, \n\toutcome VARCHAR(16) NOT NULL, \n\tdecision_id UUID, \n\tterms_hash VARCHAR(64) NOT NULL, \n\treason_code VARCHAR(64) NOT NULL, \n\treason_hash VARCHAR(64) NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_policy_activation_resolutions PRIMARY KEY (id), \n\tCONSTRAINT uq_policy_resolution_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_policy_resolution_once UNIQUE (workspace_id, request_id), \n\tCONSTRAINT uq_policy_resolution_decision UNIQUE (workspace_id, decision_id), \n\tCONSTRAINT fk_presolution_request FOREIGN KEY(workspace_id, project_id, request_id) REFERENCES policy_activation_requests (workspace_id, project_id, id), \n\tCONSTRAINT fk_presolution_actor FOREIGN KEY(workspace_id, actor_id) REFERENCES memberships (workspace_id, user_id), \n\tCONSTRAINT fk_presolution_decision FOREIGN KEY(workspace_id, decision_id) REFERENCES policy_decisions (workspace_id, id), \n\tCONSTRAINT ck_policy_activation_resolutions_policy_resolution_decision CHECK (outcome IN ('approved','rejected','withdrawn') AND ((outcome='approved')=(decision_id IS NOT NULL)))\n)\n\n", 'CREATE INDEX ix_policy_activation_resolutions_workspace_id ON policy_activation_resolutions (workspace_id)')

def _fences(head):
    for service in ("search", "model", "contact"):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
                   "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
                   f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.execute("SET LOCAL search_path=public,pg_catalog")
    for statement in FROZEN_DDL:
        op.execute(statement)
    for name in TABLES:
        op.execute(f"ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{name} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON public.{name} "
                   "USING(workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) "
                   "WITH CHECK(workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f"REVOKE ALL ON public.{name} FROM PUBLIC,buyeros_api,buyeros_worker")
        operations = "SELECT" if name == TABLES[0] else "SELECT,INSERT"
        op.execute(f"GRANT {operations} ON public.{name} TO buyeros_api")
    # Frozen least-privilege proof projection. No worker writes or full-table
    # SELECT; designation/requester/reason evidence is excluded.
    proof_columns = {
        "policy_controller_authorities": "id,workspace_id,project_id,approver_user_id,membership_version,version,status,purposes,allowed_actions,valid_from,expires_at,execution_receipt",
        "policy_activation_requests": "id,workspace_id,project_id,authority_id,authority_version,terms,terms_hash",
        "policy_activation_resolutions": "id,workspace_id,project_id,request_id,actor_id,outcome,decision_id,terms_hash",
    }
    for name, columns in proof_columns.items():
        op.execute(f"GRANT SELECT ({columns}) ON public.{name} TO buyeros_worker")
    op.execute("REVOKE UPDATE,DELETE ON public.policy_decisions,public.audit_events FROM buyeros_api,buyeros_worker")
    op.execute("REVOKE INSERT ON public.policy_decisions FROM buyeros_worker")
    _fences(revision)


def downgrade():
    db = op.get_bind()
    for name in TABLES:
        op.execute(f"ALTER TABLE public.{name} NO FORCE ROW LEVEL SECURITY")
        if db.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM public.{name})")).scalar_one():
            raise RuntimeError("0056 downgrade blocked: preserve controller policy history")
    for name in reversed(TABLES):
        op.drop_table(name,schema="public")
    # Do not restore unsafe runtime UPDATE/DELETE as an implicit rollback.
    _fences(down_revision)
