import type {OperationInput, OperationOutput} from '@/services/live/operations';

const create: OperationInput<'createProject'> = {
  path: {workspace_id: 'workspace'},
  header: {'Idempotency-Key': 'opaque-action-key'},
  body: {name: 'Sensors', company_name: 'Acme', offer: 'Industrial sensors', markets: ['DE'], language_preferences: ['en']},
};
void create;

// @ts-expect-error Project writes require an idempotency header.
const missingKey: OperationInput<'createProject'> = {path: {workspace_id: 'workspace'}, body: create.body};
void missingKey;

// @ts-expect-error ICP saves require the current offer basis revision.
const missingBasis: OperationInput<'saveICPVersion'> = {path: {workspace_id: 'workspace', project_id: 'project'}, header: {'Idempotency-Key': 'key'}, body: {offer_facts: [], requirements: [], markets: [], buyer_types: [], languages: []}};
void missingBasis;

// @ts-expect-error Approval must include a strong If-Match header.
const missingPrecondition: OperationInput<'approveICPVersion'> = {path: {workspace_id: 'workspace', icp_version_id: 'icp'}, header: {'Idempotency-Key': 'key'}, body: {content_hash: 'sha256:abc', expected_project_version: 1, confirmation: true}};
void missingPrecondition;

declare const createdProject: OperationOutput<'createProject'>;
const offerRevision: number = createdProject.offer_revision;
void offerRevision;
