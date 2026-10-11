# C61-12 local security acceptance

64required signed HTTP/runtime-PG16 cases,10Node proxy cases,8actual emitted
Chromium cases and6emitted default-protection/SSR cases pass with0fail/error/skip.
Positive discovery is64DB and8browser cases, including both Neon specs.
Current portable30/Vercel28public asset scans have0private canary hits.

The native API proves signature→canonical identity→current membership/RLS;
JWTadmin claims never grant a role. Samekid RSAAuth0/EdDSANeon caches are separate.
Revoking either mapping or membership denies scoped data immediately with
the same warm signedJWT. Directory reads return200empty without enumeration.
Signed two-admin self-demotion races leave1admin and1audit event.
UserJWTs never authorize worker service endpoints or consume their nonces.
The business proxy strips cookies/secrets, forwards HMAC only on exact worker
POSTpaths and never follows upstream redirects at the server.

Browser tests invoke actual emitted code and the unmodified SDK. ProviderHTTP
is owned synthetic protocol; the browser v1 responder is synthetic, so these
cookies are not DB/RLS or realNeon evidence. Cookie assertions inspect the
browserHTTPSorigin, excluding the shared loopback transport cookie jar.

NA01–27 exact expected/results/evidence/role/source are recorded in
artifacts/c61/C61-12-NA01-27-evidence-matrix.json. Earlier C08–11 proofs are
marked prior, not silently presented as fresh checks. Wrong test contracts
(directory404, wrongnonce table, originheader typing, loopbackcookie domain)
are retained as fixture errors. No production auth/RLS/JWT code was edited.

RealNeon exact target/email/Google, physicalSafari, issuedJWT remaining
lifetime, C13cold rollback/deletion replay, freshDBlost-response C61T03,
C26full approved-export journey and humanroleUAT remain open. Production is
not deployed/activated. Release A, Neon-only and native send are NOT ACCEPTED.
Rollback: keep these tests; disable provider admission if necessary. No
schema, UUID, FK, mapping, history or RLS change belongs to this task.
