# Neon documentation check — 2026-10-03 HK
Retrieved using Neon documentation plugin after official index discovery. No Neon resource mutated.

- https://neon.com/docs/auth/guides/plugins/jwt : Managed Better Auth browser sessions use HTTP-only cookies; authClient.token() provides external-service JWT. EdDSA/Ed25519, 15-minute token. iss/aud use auth URL origin; JWKS uses full auth base path. Custom JWT claims currently unsupported. Cross-origin cookie limitations require care.
- https://neon.com/docs/auth/reference/nextjs-server : createNeonAuth and handler() support standard Next.js server integration; cookie secret is server-only. This is not proof of Vinext/Nitro compatibility.
- https://neon.com/docs/auth/production-checklist : Verify trusted domains, production OAuth/email setup, application name and chosen verification method. Preview and production settings remain separate.

BuyerOS design inference: retain canonical User identity and workspace roles in its own DB; add verified issuer/subject mapping. Do not auto-link by email or grant workspace privileges from provider role claims. Recheck actual SDK and docs before implementation.
