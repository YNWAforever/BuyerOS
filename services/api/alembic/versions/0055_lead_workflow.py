"""Tenant-isolated manual lead preparation. Does not activate any capability."""
from alembic import op
import sqlalchemy as sa

revision = "0055_lead_workflow"
down_revision = "0054_buyer_source_checks"
branch_labels = depends_on = None

# Frozen at revision creation; deliberately independent of future ORM metadata.
TABLE_NAMES = ('lead_private_payloads', 'lead_case_states', 'lead_observations', 'lead_reviews', 'lead_review_evidence', 'lead_preparations', 'lead_preparation_revisions', 'lead_preparation_evidence', 'lead_preparation_content_reviews', 'lead_action_intents', 'pilot_budget_policies', 'pilot_cost_events', 'pilot_credit_observations', 'pilot_reconciliations')
FROZEN_DDL = (
    '\nCREATE TABLE lead_private_payloads (\n\tcompany_id UUID, \n\tperson_id UUID, \n\tcontact_id UUID, \n\tcontents JSONB, \n\tcontent_hash VARCHAR(80) NOT NULL, \n\tretention_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tredacted_at TIMESTAMP WITH TIME ZONE, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_private_payloads PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_private_payloads_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_private_payloads_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_private_payloads_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_lead_private_payloads_72d1041e99 FOREIGN KEY(workspace_id, company_id) REFERENCES companies (workspace_id, id), \n\tCONSTRAINT fk_lead_private_payloads_7971ac12d0 FOREIGN KEY(workspace_id, company_id, person_id) REFERENCES people (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_private_payloads_b3d83cfda2 FOREIGN KEY(workspace_id, company_id, contact_id) REFERENCES contact_points (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_private_payloads_7aee45d190 FOREIGN KEY(workspace_id, company_id, person_id, contact_id) REFERENCES contact_points (workspace_id, company_id, person_id, id)\n)\n\n',
    'CREATE INDEX ix_lead_payload_subject ON lead_private_payloads (workspace_id, person_id, contact_id)',
    'CREATE INDEX ix_lead_private_payloads_6f909a087e ON lead_private_payloads (workspace_id, project_id)',
    'CREATE INDEX ix_lead_private_payloads_7971ac12d0 ON lead_private_payloads (workspace_id, company_id, person_id)',
    'CREATE INDEX ix_lead_private_payloads_7aee45d190 ON lead_private_payloads (workspace_id, company_id, person_id, contact_id)',
    'CREATE INDEX ix_lead_private_payloads_b3d83cfda2 ON lead_private_payloads (workspace_id, company_id, contact_id)',
    'CREATE INDEX ix_lead_private_payloads_workspace_id ON lead_private_payloads (workspace_id)',
    "\nCREATE TABLE lead_case_states (\n\tpriority BOOLEAN DEFAULT false NOT NULL, \n\tpriority_reason VARCHAR(4000) DEFAULT '' NOT NULL, \n\tnext_action VARCHAR(200) DEFAULT '' NOT NULL, \n\tdue_on DATE, \n\tversion INTEGER DEFAULT '1' NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_case_states PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_case_states_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_case_states_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_case_states_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_case_states_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_case_states_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT uq_lead_case_one UNIQUE (workspace_id, project_id, buyer_id), \n\tCONSTRAINT ck_lead_case_states_lead_case_version CHECK (version >= 1)\n)\n\n",
    'CREATE INDEX ix_lead_case_states_227a15a959 ON lead_case_states (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_case_states_6f909a087e ON lead_case_states (workspace_id, project_id)',
    'CREATE INDEX ix_lead_case_states_workspace_id ON lead_case_states (workspace_id)',
    "\nCREATE TABLE lead_observations (\n\tclaim VARCHAR(32) NOT NULL, \n\tstance VARCHAR(16) NOT NULL, \n\tchecked_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcontent_hash VARCHAR(80) NOT NULL, \n\tpayload_id UUID, \n\tsupersedes_id UUID, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tperson_id UUID, \n\tcontact_id UUID, \n\tCONSTRAINT pk_lead_observations PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_observations_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_observations_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_observations_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_observations_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_observations_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT fk_lead_observations_7971ac12d0 FOREIGN KEY(workspace_id, company_id, person_id) REFERENCES people (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_observations_b3d83cfda2 FOREIGN KEY(workspace_id, company_id, contact_id) REFERENCES contact_points (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_observations_7aee45d190 FOREIGN KEY(workspace_id, company_id, person_id, contact_id) REFERENCES contact_points (workspace_id, company_id, person_id, id), \n\tCONSTRAINT fk_lead_observations_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_observations_ba2edd850a FOREIGN KEY(workspace_id, project_id, buyer_id, supersedes_id) REFERENCES lead_observations (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_observations_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id), \n\tCONSTRAINT ck_lead_observations_lead_observation_claim CHECK (claim IN ('employment','procurement_scope','channel_ownership')), \n\tCONSTRAINT ck_lead_observations_lead_observation_stance CHECK (stance IN ('supports','refutes','uncertain'))\n)\n\n",
    'CREATE INDEX ix_lead_observations_0c47ed3b36 ON lead_observations (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_lead_observations_227a15a959 ON lead_observations (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_observations_7aee45d190 ON lead_observations (workspace_id, company_id, person_id, contact_id)',
    'CREATE INDEX ix_lead_observations_b3d83cfda2 ON lead_observations (workspace_id, company_id, contact_id)',
    'CREATE INDEX ix_lead_observations_ba2edd850a ON lead_observations (workspace_id, project_id, buyer_id, supersedes_id)',
    'CREATE INDEX ix_lead_observations_case ON lead_observations (workspace_id, project_id, buyer_id, created_at)',
    'CREATE INDEX ix_lead_observations_e1c68316b9 ON lead_observations (recorded_by_user_id)',
    'CREATE INDEX ix_lead_observations_workspace_id ON lead_observations (workspace_id)',
    "\nCREATE TABLE lead_reviews (\n\temployment VARCHAR(16) NOT NULL, \n\tprocurement_scope VARCHAR(16) NOT NULL, \n\tchannel_ownership VARCHAR(16) NOT NULL, \n\tcase_version INTEGER NOT NULL, \n\tcontext_hash VARCHAR(80) NOT NULL, \n\tpayload_id UUID NOT NULL, \n\tprevious_review_id UUID, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tperson_id UUID, \n\tcontact_id UUID, \n\tCONSTRAINT pk_lead_reviews PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_reviews_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_reviews_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_reviews_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_reviews_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_reviews_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT fk_lead_reviews_7971ac12d0 FOREIGN KEY(workspace_id, company_id, person_id) REFERENCES people (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_reviews_b3d83cfda2 FOREIGN KEY(workspace_id, company_id, contact_id) REFERENCES contact_points (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_reviews_7aee45d190 FOREIGN KEY(workspace_id, company_id, person_id, contact_id) REFERENCES contact_points (workspace_id, company_id, person_id, id), \n\tCONSTRAINT fk_lead_reviews_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id), \n\tCONSTRAINT fk_lead_reviews_4653af34d6 FOREIGN KEY(workspace_id, project_id, buyer_id, previous_review_id) REFERENCES lead_reviews (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_reviews_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT ck_lead_reviews_lead_review_employment CHECK (employment IN ('accepted','uncertain','rejected')), \n\tCONSTRAINT ck_lead_reviews_lead_review_procurement CHECK (procurement_scope IN ('accepted','uncertain','rejected')), \n\tCONSTRAINT ck_lead_reviews_lead_review_channel CHECK (channel_ownership IN ('accepted','uncertain','rejected')), \n\tCONSTRAINT uq_lead_review_sequence UNIQUE (workspace_id, project_id, buyer_id, case_version)\n)\n\n",
    'CREATE INDEX ix_lead_reviews_0c47ed3b36 ON lead_reviews (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_lead_reviews_227a15a959 ON lead_reviews (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_reviews_4653af34d6 ON lead_reviews (workspace_id, project_id, buyer_id, previous_review_id)',
    'CREATE INDEX ix_lead_reviews_7aee45d190 ON lead_reviews (workspace_id, company_id, person_id, contact_id)',
    'CREATE INDEX ix_lead_reviews_b3d83cfda2 ON lead_reviews (workspace_id, company_id, contact_id)',
    'CREATE INDEX ix_lead_reviews_e1c68316b9 ON lead_reviews (recorded_by_user_id)',
    'CREATE INDEX ix_lead_reviews_workspace_id ON lead_reviews (workspace_id)',
    '\nCREATE TABLE lead_review_evidence (\n\treview_id UUID NOT NULL, \n\tobservation_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_review_evidence PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_review_evidence_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_review_evidence_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_review_evidence_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_review_evidence_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_review_evidence_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT uq_lead_review_ref UNIQUE (workspace_id, review_id, observation_id), \n\tCONSTRAINT fk_lead_review_evidence_a5356cf96f FOREIGN KEY(workspace_id, project_id, buyer_id, review_id) REFERENCES lead_reviews (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_review_evidence_19fa69d996 FOREIGN KEY(workspace_id, project_id, buyer_id, observation_id) REFERENCES lead_observations (workspace_id, project_id, buyer_id, id)\n)\n\n',
    'CREATE INDEX ix_lead_review_evidence_19fa69d996 ON lead_review_evidence (workspace_id, project_id, buyer_id, observation_id)',
    'CREATE INDEX ix_lead_review_evidence_227a15a959 ON lead_review_evidence (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_review_evidence_a5356cf96f ON lead_review_evidence (workspace_id, project_id, buyer_id, review_id)',
    'CREATE INDEX ix_lead_review_evidence_workspace_id ON lead_review_evidence (workspace_id)',
    "\nCREATE TABLE lead_preparations (\n\tstate VARCHAR(24) DEFAULT 'editing' NOT NULL, \n\tversion INTEGER DEFAULT '1' NOT NULL, \n\tcurrent_revision INTEGER DEFAULT '1' NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_preparations PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_preparations_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_preparations_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_preparations_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_preparations_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparations_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT ck_lead_preparations_lead_preparation_state CHECK (state IN ('editing','review_requested','reviewed','needs_review','archived'))\n)\n\n",
    'CREATE INDEX ix_lead_preparations_227a15a959 ON lead_preparations (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_preparations_workspace_id ON lead_preparations (workspace_id)',
    '\nCREATE TABLE lead_preparation_revisions (\n\tpreparation_id UUID NOT NULL, \n\trevision_number INTEGER NOT NULL, \n\tpayload_id UUID NOT NULL, \n\tlead_review_id UUID, \n\tcontext_hash VARCHAR(80) NOT NULL, \n\tcontent_hash VARCHAR(80) NOT NULL, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tperson_id UUID, \n\tcontact_id UUID, \n\tCONSTRAINT pk_lead_preparation_revisions PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_preparation_revisions_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_revisions_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_revisions_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT fk_lead_preparation_revisions_7971ac12d0 FOREIGN KEY(workspace_id, company_id, person_id) REFERENCES people (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_b3d83cfda2 FOREIGN KEY(workspace_id, company_id, contact_id) REFERENCES contact_points (workspace_id, company_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_7aee45d190 FOREIGN KEY(workspace_id, company_id, person_id, contact_id) REFERENCES contact_points (workspace_id, company_id, person_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id), \n\tCONSTRAINT uq_lead_prep_revision UNIQUE (workspace_id, preparation_id, revision_number), \n\tCONSTRAINT fk_lead_preparation_revisions_3a96933050 FOREIGN KEY(workspace_id, project_id, buyer_id, preparation_id) REFERENCES lead_preparations (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_preparation_revisions_2d06a08b24 FOREIGN KEY(workspace_id, project_id, buyer_id, lead_review_id) REFERENCES lead_reviews (workspace_id, project_id, buyer_id, id)\n)\n\n',
    'CREATE INDEX ix_lead_preparation_revisions_0c47ed3b36 ON lead_preparation_revisions (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_lead_preparation_revisions_227a15a959 ON lead_preparation_revisions (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_preparation_revisions_2d06a08b24 ON lead_preparation_revisions (workspace_id, project_id, buyer_id, lead_review_id)',
    'CREATE INDEX ix_lead_preparation_revisions_3a96933050 ON lead_preparation_revisions (workspace_id, project_id, buyer_id, preparation_id)',
    'CREATE INDEX ix_lead_preparation_revisions_7aee45d190 ON lead_preparation_revisions (workspace_id, company_id, person_id, contact_id)',
    'CREATE INDEX ix_lead_preparation_revisions_b3d83cfda2 ON lead_preparation_revisions (workspace_id, company_id, contact_id)',
    'CREATE INDEX ix_lead_preparation_revisions_e1c68316b9 ON lead_preparation_revisions (recorded_by_user_id)',
    'CREATE INDEX ix_lead_preparation_revisions_workspace_id ON lead_preparation_revisions (workspace_id)',
    '\nCREATE TABLE lead_preparation_evidence (\n\trevision_id UUID NOT NULL, \n\tobservation_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_preparation_evidence PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_preparation_evidence_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_evidence_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_preparation_evidence_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_evidence_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_evidence_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT uq_lead_prep_ref UNIQUE (workspace_id, revision_id, observation_id), \n\tCONSTRAINT fk_lead_preparation_evidence_8bf2c4e403 FOREIGN KEY(workspace_id, project_id, buyer_id, revision_id) REFERENCES lead_preparation_revisions (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_evidence_19fa69d996 FOREIGN KEY(workspace_id, project_id, buyer_id, observation_id) REFERENCES lead_observations (workspace_id, project_id, buyer_id, id)\n)\n\n',
    'CREATE INDEX ix_lead_preparation_evidence_19fa69d996 ON lead_preparation_evidence (workspace_id, project_id, buyer_id, observation_id)',
    'CREATE INDEX ix_lead_preparation_evidence_227a15a959 ON lead_preparation_evidence (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_preparation_evidence_8bf2c4e403 ON lead_preparation_evidence (workspace_id, project_id, buyer_id, revision_id)',
    'CREATE INDEX ix_lead_preparation_evidence_workspace_id ON lead_preparation_evidence (workspace_id)',
    '\nCREATE TABLE lead_preparation_content_reviews (\n\trevision_id UUID NOT NULL, \n\tcontext_hash VARCHAR(80) NOT NULL, \n\tcontent_hash VARCHAR(80) NOT NULL, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tbuyer_id UUID NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_preparation_content_reviews PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_preparation_content_reviews_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_content_reviews_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_preparation_content_reviews_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_lead_preparation_content_reviews_buyer UNIQUE (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_content_reviews_227a15a959 FOREIGN KEY(workspace_id, project_id, buyer_id, company_id) REFERENCES project_buyers (workspace_id, project_id, id, company_id), \n\tCONSTRAINT fk_lead_preparation_content_reviews_8bf2c4e403 FOREIGN KEY(workspace_id, project_id, buyer_id, revision_id) REFERENCES lead_preparation_revisions (workspace_id, project_id, buyer_id, id), \n\tCONSTRAINT fk_lead_preparation_content_reviews_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id)\n)\n\n',
    'CREATE INDEX ix_lead_preparation_content_reviews_227a15a959 ON lead_preparation_content_reviews (workspace_id, project_id, buyer_id, company_id)',
    'CREATE INDEX ix_lead_preparation_content_reviews_8bf2c4e403 ON lead_preparation_content_reviews (workspace_id, project_id, buyer_id, revision_id)',
    'CREATE INDEX ix_lead_preparation_content_reviews_e1c68316b9 ON lead_preparation_content_reviews (recorded_by_user_id)',
    'CREATE INDEX ix_lead_preparation_content_reviews_workspace_id ON lead_preparation_content_reviews (workspace_id)',
    "\nCREATE TABLE lead_action_intents (\n\tbuyer_id UUID, \n\tactor_id UUID NOT NULL, \n\taction VARCHAR(40) NOT NULL, \n\ttarget_id UUID, \n\texpected_version INTEGER, \n\tprepare_key VARCHAR(200) NOT NULL, \n\tsubmission_key VARCHAR(200) NOT NULL, \n\tfingerprint VARCHAR(80) NOT NULL, \n\tpayload_id UUID NOT NULL, \n\tstate VARCHAR(16) DEFAULT 'prepared' NOT NULL, \n\tresource_type VARCHAR(40), \n\tresource_id UUID, \n\tresource_version INTEGER, \n\tacknowledged_at TIMESTAMP WITH TIME ZONE, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_lead_action_intents PRIMARY KEY (id), \n\tCONSTRAINT uq_lead_action_intents_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_lead_action_intents_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_action_intents_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_lead_action_intents_955f07658a FOREIGN KEY(actor_id) REFERENCES users (id), \n\tCONSTRAINT fk_lead_action_intents_8fa2fed873 FOREIGN KEY(workspace_id, project_id, buyer_id) REFERENCES project_buyers (workspace_id, project_id, id), \n\tCONSTRAINT fk_lead_action_intents_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT uq_lead_intent_prepare UNIQUE (workspace_id, project_id, actor_id, prepare_key), \n\tCONSTRAINT ck_lead_action_intents_lead_intent_state CHECK (state IN ('prepared','applied','cancelled'))\n)\n\n",
    'CREATE INDEX ix_lead_action_intents_0c47ed3b36 ON lead_action_intents (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_lead_action_intents_8fa2fed873 ON lead_action_intents (workspace_id, project_id, buyer_id)',
    'CREATE INDEX ix_lead_action_intents_955f07658a ON lead_action_intents (actor_id)',
    'CREATE INDEX ix_lead_action_intents_workspace_id ON lead_action_intents (workspace_id)',
    "CREATE UNIQUE INDEX uq_lead_intent_unresolved ON lead_action_intents (workspace_id, project_id, actor_id, fingerprint) WHERE state <> 'cancelled' AND acknowledged_at IS NULL",
    "\nCREATE TABLE pilot_budget_policies (\n\tmonthly_limit NUMERIC(20, 6) NOT NULL, \n\tversion INTEGER DEFAULT '1' NOT NULL, \n\tledger_version INTEGER DEFAULT '1' NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_pilot_budget_policies PRIMARY KEY (id), \n\tCONSTRAINT uq_pilot_budget_policies_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_pilot_budget_policies_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_budget_policies_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT uq_pilot_policy_one UNIQUE (workspace_id, project_id), \n\tCONSTRAINT ck_pilot_budget_policies_pilot_limit CHECK (monthly_limit BETWEEN 0 AND 10)\n)\n\n",
    'CREATE INDEX ix_pilot_budget_policies_6f909a087e ON pilot_budget_policies (workspace_id, project_id)',
    'CREATE INDEX ix_pilot_budget_policies_workspace_id ON pilot_budget_policies (workspace_id)',
    "\nCREATE TABLE pilot_cost_events (\n\teconomic_key_hash VARCHAR(80) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tprevious_event_id UUID, \n\tnative_operation_id UUID, \n\tperiod_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstate VARCHAR(16) NOT NULL, \n\teffective_state VARCHAR(16) NOT NULL, \n\tusd_amount NUMERIC(20, 6), \n\tusd_upper_bound NUMERIC(20, 6), \n\tpayload_id UUID NOT NULL, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_pilot_cost_events PRIMARY KEY (id), \n\tCONSTRAINT uq_pilot_cost_events_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_pilot_cost_events_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_cost_events_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_pilot_cost_events_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id), \n\tCONSTRAINT fk_pilot_cost_events_e14547f0a9 FOREIGN KEY(workspace_id, project_id, previous_event_id) REFERENCES pilot_cost_events (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_cost_events_975893dcdd FOREIGN KEY(workspace_id, native_operation_id) REFERENCES budget_reservations (workspace_id, operation_id), \n\tCONSTRAINT fk_pilot_cost_events_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT uq_pilot_cost_sequence UNIQUE (workspace_id, project_id, economic_key_hash, sequence), \n\tCONSTRAINT ck_pilot_cost_events_pilot_cost_state CHECK (state IN ('committed','settled','unknown','corrected')), \n\tCONSTRAINT ck_pilot_cost_events_pilot_cost_nonnegative CHECK (usd_amount IS NULL OR usd_amount >= 0), \n\tCONSTRAINT ck_pilot_cost_events_pilot_cost_upper CHECK (usd_upper_bound IS NULL OR usd_upper_bound >= 0)\n)\n\n",
    'CREATE INDEX ix_pilot_cost_events_0c47ed3b36 ON pilot_cost_events (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_pilot_cost_events_6f909a087e ON pilot_cost_events (workspace_id, project_id)',
    'CREATE INDEX ix_pilot_cost_events_975893dcdd ON pilot_cost_events (workspace_id, native_operation_id)',
    'CREATE INDEX ix_pilot_cost_events_e14547f0a9 ON pilot_cost_events (workspace_id, project_id, previous_event_id)',
    'CREATE INDEX ix_pilot_cost_events_e1c68316b9 ON pilot_cost_events (recorded_by_user_id)',
    'CREATE INDEX ix_pilot_cost_events_workspace_id ON pilot_cost_events (workspace_id)',
    '\nCREATE TABLE pilot_credit_observations (\n\tprovider VARCHAR(100) NOT NULL, \n\tunit VARCHAR(50) NOT NULL, \n\tperiod_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\tperiod_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\tused NUMERIC(20, 6), \n\tremaining NUMERIC(20, 6), \n\tas_of TIMESTAMP WITH TIME ZONE NOT NULL, \n\tpayload_id UUID NOT NULL, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_pilot_credit_observations PRIMARY KEY (id), \n\tCONSTRAINT uq_pilot_credit_observations_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_pilot_credit_observations_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_credit_observations_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_pilot_credit_observations_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id), \n\tCONSTRAINT fk_pilot_credit_observations_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id)\n)\n\n',
    'CREATE INDEX ix_pilot_credit_observations_0c47ed3b36 ON pilot_credit_observations (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_pilot_credit_observations_e1c68316b9 ON pilot_credit_observations (recorded_by_user_id)',
    'CREATE INDEX ix_pilot_credit_observations_workspace_id ON pilot_credit_observations (workspace_id)',
    '\nCREATE TABLE pilot_reconciliations (\n\tperiod_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\tledger_version INTEGER NOT NULL, \n\tledger_hash VARCHAR(80) NOT NULL, \n\tcoverage_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcoverage_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\tshared_usage_known BOOLEAN NOT NULL, \n\tpayload_id UUID NOT NULL, \n\trecorded_by_user_id UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tproject_id UUID NOT NULL, \n\tCONSTRAINT pk_pilot_reconciliations PRIMARY KEY (id), \n\tCONSTRAINT uq_pilot_reconciliations_tenant UNIQUE (workspace_id, id), \n\tCONSTRAINT uq_pilot_reconciliations_project UNIQUE (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_reconciliations_6f909a087e FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id), \n\tCONSTRAINT fk_pilot_reconciliations_0c47ed3b36 FOREIGN KEY(workspace_id, project_id, payload_id) REFERENCES lead_private_payloads (workspace_id, project_id, id), \n\tCONSTRAINT fk_pilot_reconciliations_e1c68316b9 FOREIGN KEY(recorded_by_user_id) REFERENCES users (id)\n)\n\n',
    'CREATE INDEX ix_pilot_reconciliations_0c47ed3b36 ON pilot_reconciliations (workspace_id, project_id, payload_id)',
    'CREATE INDEX ix_pilot_reconciliations_e1c68316b9 ON pilot_reconciliations (recorded_by_user_id)',
    'CREATE INDEX ix_pilot_reconciliations_workspace_id ON pilot_reconciliations (workspace_id)',
)


def _fences(head):
    for service in ("search", "model", "contact"):
        op.execute(
            f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$"
        )


def upgrade():
    op.create_unique_constraint("uq_project_buyers_lead_company", "project_buyers",
                                ["workspace_id", "project_id", "id", "company_id"])
    op.create_unique_constraint("uq_people_lead_company", "people", ["workspace_id", "company_id", "id"])
    op.create_unique_constraint("uq_contact_lead_company", "contact_points", ["workspace_id", "company_id", "id"])
    op.create_unique_constraint("uq_contact_lead_person", "contact_points",
                                ["workspace_id", "company_id", "person_id", "id"])
    mutable = {"lead_case_states", "lead_preparations", "lead_action_intents", "pilot_budget_policies"}
    for statement in FROZEN_DDL:
        op.execute(statement)
    for name in TABLE_NAMES:
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {name} "
            "USING(workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) "
            "WITH CHECK(workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)"
        )
        op.execute(f"REVOKE ALL ON {name} FROM PUBLIC,buyeros_api,buyeros_worker")
        op.execute(f"GRANT SELECT,INSERT ON {name} TO buyeros_api")
        if name in mutable:
            op.execute(f"GRANT UPDATE ON {name} TO buyeros_api")
    # Existing native workers check whether a project is in the disabled pilot
    # before reserving a budget. This policy row contains no private evidence.
    op.execute("GRANT SELECT ON pilot_budget_policies TO buyeros_worker")
    # Only private contents may be cleared, after checking the canonical
    # subject's deadline and the caller's tenant scope. Journal metadata stays.
    op.execute("""
    CREATE FUNCTION public.buyeros_redact_lead_subject(p_workspace uuid,p_kind text,p_id uuid)
    RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE n integer;
    BEGIN
      IF p_workspace IS DISTINCT FROM NULLIF(current_setting('app.workspace_id',true),'')::uuid THEN
        RAISE EXCEPTION 'tenant scope required' USING ERRCODE='42501';
      END IF;
      IF p_kind='contact_point' THEN
        IF NOT EXISTS(SELECT 1 FROM public.contact_points WHERE workspace_id=p_workspace AND id=p_id
                      AND retention_expires_at<=CURRENT_TIMESTAMP) THEN
          RAISE EXCEPTION 'contact not expired' USING ERRCODE='42501';
        END IF;
      ELSIF p_kind='person' THEN
        IF NOT EXISTS(SELECT 1 FROM public.people WHERE workspace_id=p_workspace AND id=p_id
                      AND retention_expires_at<=CURRENT_TIMESTAMP) THEN
          RAISE EXCEPTION 'person not expired' USING ERRCODE='42501';
        END IF;
      ELSIF p_kind='source_document' THEN
        IF NOT EXISTS(SELECT 1 FROM public.source_documents WHERE workspace_id=p_workspace AND id=p_id
                      AND retention_until<=CURRENT_TIMESTAMP) THEN
          RAISE EXCEPTION 'source not expired' USING ERRCODE='42501';
        END IF;
      ELSIF p_kind='lead_payload' THEN
        IF NOT EXISTS(SELECT 1 FROM public.lead_private_payloads WHERE workspace_id=p_workspace AND id=p_id
                      AND retention_expires_at<=CURRENT_TIMESTAMP) THEN
          RAISE EXCEPTION 'payload not expired' USING ERRCODE='42501';
        END IF;
      ELSIF p_kind='offer_document' THEN
        IF NOT EXISTS(SELECT 1 FROM public.offer_documents WHERE workspace_id=p_workspace AND id=p_id
                      AND (deleted_at IS NOT NULL OR retention_until<=CURRENT_TIMESTAMP)) THEN
          RAISE EXCEPTION 'offer document not expired or deleted' USING ERRCODE='42501';
        END IF;
      ELSE RAISE EXCEPTION 'unsupported subject' USING ERRCODE='42501';
      END IF;
      UPDATE public.lead_private_payloads SET contents=NULL,redacted_at=CURRENT_TIMESTAMP
      WHERE workspace_id=p_workspace AND contents IS NOT NULL AND (
        (p_kind='contact_point' AND contact_id=p_id) OR
        (p_kind='person' AND person_id=p_id) OR
        (p_kind='lead_payload' AND id=p_id AND retention_expires_at<=CURRENT_TIMESTAMP) OR
        (p_kind='source_document' AND contents->'source_document_ids' @> jsonb_build_array(p_id::text)) OR
        (p_kind='offer_document' AND contents->'offer_document_ids' @> jsonb_build_array(p_id::text)) OR
        id IN (
          SELECT i.payload_id FROM public.lead_action_intents i
          JOIN public.lead_observations o ON o.workspace_id=i.workspace_id
            AND o.project_id=i.project_id AND o.id=i.resource_id
          WHERE i.workspace_id=p_workspace AND i.resource_type='lead_observation'
            AND ((p_kind='person' AND o.person_id=p_id)
              OR (p_kind='contact_point' AND o.contact_id=p_id))
        )
      );
      GET DIAGNOSTICS n=ROW_COUNT;
      RETURN n;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_redact_lead_subject(uuid,text,uuid) FROM PUBLIC,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_redact_lead_subject(uuid,text,uuid) TO buyeros_api,buyeros_worker;
    """)
    op.execute("""
    CREATE FUNCTION public.buyeros_expire_due_lead_payloads(p_workspace uuid,p_limit integer)
    RETURNS TABLE(subject_id uuid,erased integer) LANGUAGE plpgsql SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$
    DECLARE candidate record;
    BEGIN
      IF p_workspace IS NULL OR p_workspace IS DISTINCT FROM
         NULLIF(current_setting('app.workspace_id',true),'')::uuid THEN
        RAISE EXCEPTION 'tenant scope required' USING ERRCODE='42501';
      END IF;
      IF p_limit IS NULL OR p_limit<1 OR p_limit>100 THEN
        RAISE EXCEPTION 'bounded retention required' USING ERRCODE='22023';
      END IF;
      FOR candidate IN SELECT p.id FROM public.lead_private_payloads p
        WHERE p.workspace_id=p_workspace AND p.retention_expires_at<=CURRENT_TIMESTAMP
          AND p.contents IS NOT NULL
        ORDER BY p.retention_expires_at,p.id LIMIT p_limit FOR UPDATE SKIP LOCKED
      LOOP
        subject_id:=candidate.id;
        erased:=public.buyeros_redact_lead_subject(p_workspace,'lead_payload',candidate.id);
        RETURN NEXT;
      END LOOP;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_expire_due_lead_payloads(uuid,integer) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_expire_due_lead_payloads(uuid,integer) TO buyeros_api,buyeros_worker;
    """)
    _fences(revision)


def downgrade():
    db = op.get_bind()
    for name in reversed(TABLE_NAMES):
        op.execute(f"ALTER TABLE {name} NO FORCE ROW LEVEL SECURITY")
        if db.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {name})")).scalar_one():
            raise RuntimeError("0055 downgrade blocked: preserve lead evidence and original intents")
    op.execute("DROP FUNCTION public.buyeros_expire_due_lead_payloads(uuid,integer)")
    op.execute("DROP FUNCTION public.buyeros_redact_lead_subject(uuid,text,uuid)")
    for name in reversed(TABLE_NAMES):
        op.drop_table(name)
    for name, table in (
        ("uq_contact_lead_person", "contact_points"), ("uq_contact_lead_company", "contact_points"),
        ("uq_people_lead_company", "people"), ("uq_project_buyers_lead_company", "project_buyers"),
    ):
        op.drop_constraint(name, table, type_="unique")
    _fences(down_revision)
