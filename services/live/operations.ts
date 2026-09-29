import type {operations} from '@/services/generated/buyeros-api';
import {operationRoutes} from '@/services/generated/operation-routes';
import {LiveCancelled, type LiveClient} from './client';
import type {WriteContext as CapturedWriteContext} from './session';

type Params<K extends keyof operations> = operations[K] extends {parameters: infer P} ? P : never;
type PathOf<K extends keyof operations> = Params<K> extends {path: infer P} ? P : never;
type HeaderOf<K extends keyof operations> = Params<K> extends {header: infer H} ? H : never;
type QueryOf<K extends keyof operations> = Params<K> extends {query?: infer Q} ? Q : never;
type BodyOf<K extends keyof operations> = operations[K] extends {requestBody: {content: {'application/json': infer B}}} ? B : never;
type RequiredField<Name extends string, T> = [T] extends [never] ? object : {[P in Name]: T};
type OptionalField<Name extends string, T> = [T] extends [never] ? object : {[P in Name]?: T};
export type OperationInput<K extends keyof operations> = RequiredField<'path', PathOf<K>> & RequiredField<'header', HeaderOf<K>> & RequiredField<'body', BodyOf<K>> & OptionalField<'query', QueryOf<K>>;
type SuccessOf<K extends keyof operations> = operations[K] extends {responses: infer R} ? R[keyof R & (200 | 201 | 202 | 204)] : never;
type EnvelopeOf<T> = T extends {content: {'application/json': infer E}} ? E : never;
export type OperationOutput<K extends keyof operations> = EnvelopeOf<SuccessOf<K>> extends {data: infer D} ? D : void;
export type WriteContext = CapturedWriteContext & {getToken: () => Promise<string>; isCurrent: () => boolean};

/** This is the one typed boundary from generated OpenAPI operations to live bearer requests. */
export function createOperationClient(client: Pick<LiveClient, 'request'>) {
  return {
    async requestOperation<K extends keyof operations>(id: K, input: OperationInput<K>, ctx: WriteContext): Promise<OperationOutput<K>> {
      const guard = () => {if (ctx.signal.aborted || !ctx.isCurrent()) throw new LiveCancelled('scope changed');};
      guard();
      const route = operationRoutes[id];
      const parts = input as {path?: Record<string, string>; query?: Record<string, string | number | boolean | null | undefined>; header?: Record<string, string>; body?: unknown};
      if (parts.path?.workspace_id && parts.path.workspace_id !== ctx.workspace) throw new LiveCancelled('workspace changed');
      if (parts.path?.project_id && ctx.project && parts.path.project_id !== ctx.project) throw new LiveCancelled('project changed');
      const path = route.path.replace(/\{([^}]+)\}/g, (_, name: string) => {
        const value = parts.path?.[name];
        if (!value) throw new Error(`Missing path parameter: ${name}`);
        return encodeURIComponent(value);
      });
      const query = new URLSearchParams();
      for (const [name, value] of Object.entries(parts.query ?? {})) if (value !== null && value !== undefined) query.set(name, String(value));
      const token = await ctx.getToken();
      guard();
      const value = await client.request<OperationOutput<K>>({
        path: path + (query.size ? `?${query}` : ''), method: route.method,
        token, scope: ctx.identity, signal: ctx.signal, body: parts.body,
        idempotencyKey: parts.header?.['Idempotency-Key'], ifMatch: parts.header?.['If-Match'],
      });
      guard();
      return value;
    },
  };
}
