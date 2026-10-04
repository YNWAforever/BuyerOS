/** Strict server-runtime boundary for the pinned SDK; no environment read on import. */
export type RealRuntimeEnvironment = Readonly<Record<string, string | undefined>>;
export type RealSDKConfiguration = Readonly<{
  baseUrl: string;
  cookies: Readonly<{secret: string; sameSite: 'lax'; sessionDataTtl: 300}>;
}>;
export type RealTrustConfiguration = Readonly<{
  issuer: string;
  audience: string;
  jwksUrl: string;
  algorithm: 'EdDSA';
  keyType: 'OKP';
  curve: 'Ed25519';
}>;
export type RealRuntimeDescription = Readonly<{
  fingerprint: string;
  expiresAt: string;
  projectId: string;
  branchId: string;
  authId: string;
  trust: RealTrustConfiguration;
  external_verified: false;
}>;
export type RealRuntimeConfiguration = Readonly<
  Omit<RealRuntimeDescription, 'external_verified'> & {sdk: RealSDKConfiguration}
>;
export function readRealRuntimeConfiguration(
  environment: RealRuntimeEnvironment,
  now?: number,
): RealRuntimeConfiguration;
export function createRealAuthRuntime<T>(options: {
  readEnvironment: () => RealRuntimeEnvironment;
  createAuth: (configuration: RealSDKConfiguration) => T;
  now?: () => number;
}): Readonly<{
  getAuth: () => T;
  describe: () => RealRuntimeDescription;
}>;
