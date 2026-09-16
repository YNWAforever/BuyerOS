export {httpClient} from './mock-client';
export {createLiveClient, LiveError, LiveCancelled} from './live/client';
// Future server adapters must independently enforce tenant identity, policy,
// suppression, reservations, idempotency and immutable approval revisions.
