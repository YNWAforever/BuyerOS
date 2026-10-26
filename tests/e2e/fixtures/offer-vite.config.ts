import {fileURLToPath} from 'node:url';
import {defineConfig, mergeConfig} from 'vite';
import base from '../../../vite.config';

// Keep this dev harness's optimized RSC/client modules separate from builds and
// other browser fixtures. Keep it under node_modules so Nitro recognizes the
// prebundled dependencies and does not transform them a second time.
export default defineConfig(async env => mergeConfig(typeof base === 'function' ? await base(env) : base, {
  root: fileURLToPath(new URL('../../../', import.meta.url)),
  cacheDir: fileURLToPath(new URL('../../../node_modules/.vite-offer-profile', import.meta.url)),
  server: {watch: {ignored: ['**/.venv/**', '**/work/**', '**/outputs/**', '**/test-results/**', '**/artifacts/**']}},
}));
