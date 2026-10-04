import {getAuth} from '../../../../lib/neon-real-runtime/server';

type Handlers = ReturnType<ReturnType<typeof getAuth>['handler']>;
function handler(method: keyof Handlers): Handlers['GET'] {
  return (...args) => getAuth().handler()[method](...args);
}
export const GET = handler('GET');
export const POST = handler('POST');
export const PUT = handler('PUT');
export const DELETE = handler('DELETE');
export const PATCH = handler('PATCH');
