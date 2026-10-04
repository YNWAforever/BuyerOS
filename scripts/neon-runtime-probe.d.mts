import type {RealRuntimeConfiguration} from './neon-real-runtime.mjs';
export function assertRuntimeProbeTarget(configuration: RealRuntimeConfiguration): void;
export function installProbeFetchGuard(host?: {fetch: typeof fetch}): Readonly<{
  metrics: () => Readonly<{blocked: number; forwarded: 0; fixture_only: true}>;
}>;
