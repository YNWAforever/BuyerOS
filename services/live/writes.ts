/** Sequence project/profile writes under one captured, abortable workspace context. */
import {toIcpSaveRequest, toProjectCreate, ProfileError, type Offerish} from './profile';
import type {components} from '@/services/generated/buyeros-api';
import {LiveCancelled, type LiveClient} from './client';
import {createOperationClient, type WriteContext} from './operations';
import type {SessionScope} from './session';

interface Deps {client: Pick<LiveClient, 'request'>; session: SessionScope; idempotencyKey: string;}
type OfferFact=components['schemas']['OfferFact'];
export interface SavedProject {id: string; offer_revision: number; version?: number;}
export interface SavedIcpVersion {id: string; number: number; content_hash: string;}
export class ProfileStepError extends Error {
  constructor(public readonly project: SavedProject, public readonly cause: unknown) {super('Project saved; profile still needs saving');}
}
function context(session: SessionScope): WriteContext {
  const captured = session.captureWriteContext();
  return {
    ...captured,
    getToken: async () => {const token = session.token(); if (!token) throw new LiveCancelled('sign-in expired'); return token;},
    isCurrent: () => session.isCurrent(captured.identity),
  };
}
function offerRevision(project: SavedProject): number {
  if (!Number.isInteger(project.offer_revision) || project.offer_revision < 1) throw new ProfileError('Project offer revision unavailable');
  return project.offer_revision;
}
export type SaveProfileInput = Deps & {offer: Offerish; documentIds?: string[]; documentFacts?: OfferFact[]} & (
  | {mode: 'create'; projectId?: never; expectedProjectVersion?: never; basisOfferRevision?: never}
  | {mode: 'edit'; projectId: string; expectedProjectVersion: number; basisOfferRevision: number; parentIcpVersionId?: string}
);

export async function saveProfile(input: SaveProfileInput): Promise<{project: SavedProject; icpVersion: SavedIcpVersion}> {
  const {client, session, offer, idempotencyKey} = input;
  const ctx = context(session);
  const operations = createOperationClient(client);
  // Map and validate the entire form before the first persistent step.
  const projectBody = toProjectCreate(offer);
  const plainIcpBody = toIcpSaveRequest(offer);
  const documentIds=[...new Set(input.documentIds??[])];
  if(documentIds.length>20)throw new ProfileError('Select at most 20 offer documents');
  const documentFacts=input.documentFacts??[];
  const icpBody={...plainIcpBody,offer_document_ids:documentIds,
    offer_facts:plainIcpBody.offer_facts.map(fact=>documentFacts.find(candidate=>
      candidate.field===fact.field&&candidate.value===fact.value&&
      candidate.source_document_id&&documentIds.includes(candidate.source_document_id))??fact)};
  let project: SavedProject;
  if (input.mode === 'create') {
    project = await operations.requestOperation('createProject', {
      path: {workspace_id: ctx.workspace}, header: {'Idempotency-Key': idempotencyKey}, body: projectBody,
    }, ctx);
  } else {
    if (!Number.isSafeInteger(input.expectedProjectVersion) || input.expectedProjectVersion < 1
      || !Number.isSafeInteger(input.basisOfferRevision) || input.basisOfferRevision < 1) {
      throw new ProfileError('Project version and offer basis are required for edit');
    }
    if (ctx.project && ctx.project !== input.projectId) throw new LiveCancelled('project changed');
    project = await operations.requestOperation('updateProject', {
      path: {workspace_id: ctx.workspace, project_id: input.projectId},
      header: {'Idempotency-Key': idempotencyKey, 'If-Match': `"${input.expectedProjectVersion}"`},
      body: {...projectBody, website: offer.website?.trim() || null},
    }, ctx);
    if (project.id !== input.projectId || offerRevision(project) < input.basisOfferRevision) {
      throw new ProfileError('Updated project basis is inconsistent');
    }
  }
  if (!ctx.isCurrent() || ctx.signal.aborted) throw new LiveCancelled('scope changed');
  // A deliberately new project can be created while another is selected; keep the
  // original generation guard but bind this second step to the returned project.
  const projectCtx = input.mode === 'create' ? {...ctx, project: project.id} : ctx;
  try {
    const icpVersion = await operations.requestOperation('saveICPVersion', {
      path: {workspace_id: ctx.workspace, project_id: project.id},
      header: {'Idempotency-Key': idempotencyKey},
      body: {...icpBody, basis_offer_revision: offerRevision(project),
        ...(input.mode === 'edit' && input.parentIcpVersionId ? {parent_icp_version_id: input.parentIcpVersionId} : {})},
    }, projectCtx);
    return {project, icpVersion};
  } catch (error) {
    if (error instanceof LiveCancelled) throw error;
    throw new ProfileStepError(project, error);
  }
}
export async function approveProfile(input: Deps & {project: {id: string; version: number}; icpVersion: SavedIcpVersion}): Promise<{id: string; status: string}> {
  const {client, session, icpVersion, idempotencyKey} = input;
  const ctx = context(session);
  if (ctx.project !== input.project.id) throw new LiveCancelled('project changed');
  return createOperationClient(client).requestOperation('approveICPVersion', {
    path: {workspace_id: ctx.workspace, icp_version_id: icpVersion.id},
    header: {'Idempotency-Key': idempotencyKey, 'If-Match': `"${icpVersion.number}"`},
    body: {content_hash: icpVersion.content_hash, confirmation: true, expected_project_version: input.project.version},
  }, ctx);
}

export async function archiveProject(input: Deps & {projectId: string; version: number; reason: string}) {
  const reason=input.reason.trim();
  if(reason.length<3||reason.length>2000)throw new ProfileError('Archive reason must be 3–2000 characters');
  if(!Number.isSafeInteger(input.version)||input.version<1)throw new ProfileError('Project version required');
  const ctx=context(input.session);
  if(ctx.project!==input.projectId)throw new LiveCancelled('project changed');
  return createOperationClient(input.client).requestOperation('archiveProject',{
    path:{workspace_id:ctx.workspace,project_id:input.projectId},
    header:{'Idempotency-Key':input.idempotencyKey,'If-Match':`"${input.version}"`},
    body:{reason},
  },ctx);
}
