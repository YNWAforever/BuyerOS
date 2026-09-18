// services/live/writes.ts
/** Sequence the project/profile write calls. No UI, no storage, no demo data. */
import {toIcpSaveRequest, toProjectCreate, type Offerish} from './profile';
import type {LiveClient} from './client';
import type {SessionScope} from './session';

interface Deps {
  client: Pick<LiveClient, 'request'>;
  session: Pick<SessionScope, 'current' | 'token' | 'identity'>;
  idempotencyKey: string;
}

export interface SavedProject {
  id: string;
}

export interface SavedIcpVersion {
  id: string;
  number: number;
  content_hash: string;
}

export async function saveProfile(
  input: Deps & {offer: Offerish; projectId?: string},
): Promise<{project: SavedProject; icpVersion: SavedIcpVersion}> {
  const {client, session, offer, idempotencyKey} = input;
  const current = session.current();
  const workspace = current.workspace;
  const token = session.token();
  // "Create or select": the caller may name a project, else the session's selected project is used,
  // and only when neither exists is a project created.
  let projectId = input.projectId ?? current.project ?? undefined;
  let project: SavedProject;
  if (projectId) {
    project = {id: projectId};
  } else {
    project = await client.request<SavedProject>({
      path: `/v1/workspaces/${workspace}/projects`, method: 'POST', scope: session.identity(),
      token, body: toProjectCreate(offer), idempotencyKey,
    });
    projectId = project.id;
  }
  const icpVersion = await client.request<SavedIcpVersion>({
    path: `/v1/workspaces/${workspace}/projects/${projectId}/icp-versions`, method: 'POST', scope: session.identity(),
    token, body: toIcpSaveRequest(offer), idempotencyKey,
  });
  return {project, icpVersion};
}

export async function approveProfile(
  input: Deps & {project: {id: string}; icpVersion: SavedIcpVersion},
): Promise<{id: string; status: string}> {
  const {client, session, icpVersion, idempotencyKey} = input;
  const workspace = session.current().workspace;
  return client.request<{id: string; status: string}>({
    path: `/v1/workspaces/${workspace}/icp-versions/${icpVersion.id}/approve`, method: 'POST', scope: session.identity(),
    token: session.token(), idempotencyKey, ifMatch: `"${icpVersion.number}"`,
    body: {content_hash: icpVersion.content_hash, confirmation: true},
  });
}
