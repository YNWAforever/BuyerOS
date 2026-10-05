# N00 transport coverage — local observations only

| Surface | Current evidence | Remaining disposition |
| --- | --- | --- |
| Dedicated Chromium page HTTP | Exact-origin route + durable owned gateway; original3 cases pass | Fixture-only, not OS containment |
| Same-origin and foreign-loopback native WebSocket | RED4 physical bypass upgrades; GREEN0 across refresh; positive control1 | Fixed only in dedicated audit-neon-execution context |
| Service workers | Existing config block; no script request or worker | No real Google/background network acceptance |
| Pinned SDK / fixed Node fixture CLI | Counted gateway;4 physical auth requests; inherited secrets stripped | Arbitrary provider CLI is not this helper |
| Unknown write + reconstructed journal |1commit, held retry refused across restart | Do not erase journal; real reconcile/cleanup still needed |
| Node http.get | Owned sink receives1 while global fetch guard forwarded0 | Reproduced OPEN; actual net/https/undici/TLS/worker subprocess paths also need audit |
| Playwright APIRequestContext | Owned sink receives1; context HTTP callbacks0 | Reproduced OPEN; must use explicit counted transport, not assume browser routing applies |
| Browser WebRTC/DNS/OS/background egress | Not exercised by these auth fixture cases | OPEN; no all-channel claim |
| Actual Neon/Google/control-plane cleanup | No new resources/accounts/readbacks | Fresh implementation/review and concrete authorization required |

Playwright documents separate [context WebSocket routing](https://playwright.dev/docs/api/class-browsercontext#browser-context-route-web-socket), before sockets are created, and [service-worker routing limits](https://playwright.dev/docs/network#missing-network-events-and-service-workers). This patch uses routeWebSocket close without connectToServer; it neither mocks a successful provider socket nor replaces missing real identity evidence.

## Next bounded local brief

Preserve the single journal/migration/domain API owners. Build one fixture-only explicit native transport into the existing owned gateway; before every physical allowed HTTP hop reserve/fsync, validate method/full canonical intent/exact target/TTL, manual redirects, hold uncertainty and count readback/reconciliation. Deny direct egress in an owned disposable process/container boundary; prove raw Node/APIRequestContext/CLI attempts fail before dispatch and inherited credentials do not enter it. Do not treat HTTP_PROXY or a global fetch monkey patch as sufficient for transports that ignore them. The parent/control/browser boundary must be included, not just one child container. This is a local preparation brief, not implemented containment or authority to run a real provider CLI.

No real URLs, credentials, production DSNs, identity links, account grants or owner approval are filled. OS topology/egress exceptions require review against actual runtime needs; full N00 stays OPEN until separate evidence establishes them.
