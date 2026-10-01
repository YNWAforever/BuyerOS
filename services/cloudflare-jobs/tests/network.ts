import { setupNetwork } from '@msw/cloudflare';

/** Local test transport only. No fixture is used by deployed controllers. */
export const network = setupNetwork();
