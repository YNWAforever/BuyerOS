# C61-11 session boundary, local proof and rollback

This runbook retains the historical C61-11 local implementation proof and its
limits, not real Neon or production acceptance. Its public PR checkpoint was
1b21dc4, before public push authorization. Its unaccepted Release A, Neon-only
and native-send gates describe that checkpoint, not current deployment status.

## Provider and cookie boundary

BUYEROS_AUTH_PROVIDER defaults to `neon`. Public browser login is Neon only;
explicit `auth0` is unavailable. Neon requires the separately validated C61-08
server configuration and BUYEROS_NEON_AUTH_ROUTE_ENABLED=1. Public configuration
contains only `authPath:'/api/auth'`, the approved `socialInitOrigin` and
`socialInitPath`; the cookie secret, full server configuration, expected target
bindings and test credentials remain server-side. Invalid/missing Neon config
is unavailable and does not fall back to Auth0. The API separately defaults
BUYEROS_AUTH_MODE to `neon` and retains explicit Auth0/dual compatibility modes.
These source defaults do not change any deployed environment variable, account,
issuer, provider or production setting.

The pinned unmodified@neondatabase/auth0.5.0-beta browser implementation emits
sessionData through BetterAuth's broadcast system, including session.token.
Its installed dist/adapter-core-CZ8saNEY.mjs lines558–578 are the reviewed
compatibility evidence. BuyerOS therefore calls the unmodified server SDK's
same-origin/get-session,/token,/sign-in/email,/sign-in/social,/sign-out routes
with credentials:same-origin and cache:no-store. It imports no patched SDK or
the token-broadcasting browser adapter. Cookie flags, upstream status/errors
and the API's signature/issuer/audience/JWKS/DB authority remain authoritative.
Google uses the provider's actual URL response and a bounded session verifier;
Google's real flow has not been exercised. No anonymous token fallback exists.

JWTs exist only in adapter/SessionScope memory. Browser decoding reads subject
and finite expiry metadata only; it grants no memberships/roles. The API must
verify the signature and current active identity/membership for every request.
Initialization remains one loading state until cookie hydration settles;
provider errors never become an empty membership list. Twenty renewals share
one promise. Authenticated explicit401 permits one retry of the original
serialized body, If-Match and intent key. Multipart keeps its first browser
body/boundary and freezes retry fields. Writes without an intent key, accepted
responses, lost/network responses,403/409/503 are never automatically replayed.

## Invalidation, navigation and dirty draft

Scope generation and AbortController reject A-B-A, logout, old renewal and old
callback completion. An unmounted/replaced callback consumer cannot publish.
Cross-tab messages are exactly{type:'logout'} or{type:'invalidated'}; the
actual built Chromium observer verifies these payloads. The older-browser
storage fallback also carries only an event. Safari hardware/storage capability
still requires real verification. Logout failure remains a failure; a per-tab
invalidated marker prevents an old cookie from silently hydrating afterreload.
A new valid sign-in transaction is required to clear that marker.

Return paths canonicalize to same-site/app only. BuyerOS return state is
single-use and expires in10minutes; only state/returnPath/createdAt enter its
per-tab sessionStorage transaction. Password, JWT and OAuth verifier are not
stored. Callback verifier goes only to the SDK cookie exchange.

Local logout/project/workspace/route transitions consume the existing draft
Save/Discard/Cancel guard. A remote logout clears auth/scope/polling immediately
and first captures unsaved text. The private per-tab recovery buffer contains
actor/workspace/project/draft/revision/version and text only: no JWT, grants,
intent or automatic writes. Recovery requires the same exact principal/scope
and a successful scoped server read. A changed server revision is shown for
comparison; approval is not restored. Explicit Discard and successful save
remove the buffer. Capacity/storage failures retain memory without evicting
another dirty draft; persistence across a hard reload still depends on browser
sessionStorage capacity. The existing beforeunload guard remains. Data has not
been copied into any production fixture or provider.

## Evidence levels and limits

The final Node gate covers session, callback SSR and scope-poller behavior;
legacy Auth0 crypto and live adapter checks remain separate. The emitted
Vercel payload is compiled locally with a positive public-asset/private-canary
scan. The built Chromium fixture uses that actual function and the unpatched
server SDK with an owned, deny-external-network synthetic provider protocol.
Its/v1 responder is synthetic and is not DB tenant/RLS evidence. C61-10's110
signed HTTP/DB cases provide earlier scoped API proof; C61-12 must complete
the next security matrix. No fresh whole API suite is claimed byC61-11.

Built checks coveremail→SDK cookie→JWT→synthetic API→reload/deep link→two-tab
logout, event payloads, dirty Cancel/Discard and remote-logout recovery after
reauthentication. These are not real email/Google/Safari/Neon target acceptance.
JWTs already issued can remain valid at the API until their expiry or current
mapping/membership rejection. Their real remaining lifetime and remote session
logout effects must be measured; local UI clearing does not prove global JWT
revocation. C61T-03 run/outbox counters are currently synthetic transport
observations, not a fresh committed DB lost-response proof.

## Rollback

Use the reviewed compatible app/provider artifact and stop new Neon admission.
The C61-11 checkpoint described a dual-compatible client for existing Auth0
users. The current browser is Neon only; an Auth0 rollback needs a reviewed
compatible app artifact, not `BUYEROS_AUTH_PROVIDER=auth0` on this client.
An Auth0 rollback is not a login rollback for Neon-only accounts. That population requires
the C61-13 compatible Neon artifact rehearsal before cutover. Clear in-memory
client auth and the bounded return/invalidation transaction when intentionally
changing compatible provider configuration. Preserve private draft recovery
until the same authenticated principal can compare it. Never delete identity
mappings, canonical User UUIDs, historical FKs, revocations or memberships.
This task introduces no DB migration and performs no deployment/auth change.
