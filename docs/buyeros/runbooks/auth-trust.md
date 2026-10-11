# C61-10 exact provider trust and rollback

Local signed protocol/API/PG delivery only. No provider is enabled and no real
Neon issuer/audience/JWKS is supplied. The runtime default remainsAuth0RS256.
The prior898-case whole-API proof is C61-09; the current focused110auth/DB gate
has positive110discovery and0fail/error/skip. A later whole-candidate gate is
still required before release.

BUYEROS_AUTH_MODE accepts auth0(default), dual or neon. Auth0 uses its existing
issuer/audience and derived JWKS contract withRSA/RS256. Neon requires all of:
BUYEROS_NEON_ISSUER, BUYEROS_NEON_AUDIENCE, BUYEROS_NEON_JWKS_URL, and separately
reviewed BUYEROS_NEON_EXPECTED_ISSUER/AUDIENCE/JWKS_URL. Values must be exact;
Neon endpoints are HTTPS on.neon.tech. There is no Auth0/Neon fallback for
missing or invalid configuration. Fixture trust and test credentials refuse
Neon initialization. Each provider owns its own issuer/JWKS cache; a samekid
from another issuer cannot select its key.

Obtain issuer/audience from an independently verified real target token and
the JWKS/branch from the authorized manifest, as specified byC61-07. Never
substitute a fixture value, infer aud from a request, remove audience checking,
or let token jku/x5u/jwk/crit choose key material. The official pinned contract
permits NeonEdDSA only with publicOKP/Ed25519 keys; Auth0 remainsRS256/RSA.
Private/encryption/wrong-algorithm/wrong-curve keys are refused. NumericDate
claims must be finite JSON numbers, not booleans/coerced strings. Exact string
subject and issuer/audience are checked after signature verification. Invalid
claims/headers/configuration return401 through the existing error envelope.
JWT roles never grant BuyerOS membership or workspace roles.

Dual mode additionally requires BUYEROS_AUTH_MIGRATION_EXPIRES_AT as a future
Unix timestamp in decimal seconds. There is no default deadline. An already
warm verifier checks this deadline on every request; at/after it the dual
window refuses tokens rather than silently extending or selecting a fallback.
Operators must deliberately choose an accepted compatible target before the
deadline. JWKS TTL, bounded unknownkid refresh, concurrent cold coalescing and
hard stale ceiling remain enforced; outages never bypass signature checking.

Review env bindings and source hashes, then run required suites and the
authorized real-Neon/browser gates. This task does not alter deployed auth,
migrate a production DB, provision accounts or consume provider quota.

Rollback to the known Auth0 trust settings/app artifact, without widening its
issuer/audience/algorithms. Keep the active-mapping resolver and canonical UUIDs,
all historical FKs, Neon-only users and revoked identities. Auth0-only rollback
does not prove a Neon-only user can still log in: the compatible provider/client
rehearsal and actual user login remainC61-13 gates. Already-issued provider JWT
lifetime is distinct from client logout; actual mapping/membership revocation
is rechecked on the next business request.

Contract source: [Neon JWT plugin](https://neon.com/docs/auth/guides/plugins/jwt)
and the existing reviewedC61-07 decision. Exact real target remains unset.
