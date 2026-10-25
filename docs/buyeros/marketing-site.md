# BuyerOS bilingual marketing site

The public site has eight pages per language: home, features, how-it-works,
pricing, FAQ, demo, privacy and terms, at `/zh-HK` and `/en`. `/` and bare public
aliases redirect to zh-HK. `/login` and language login aliases lead to `/app`.
The primary CTA is Request a demo / 預約示範. Prices are a contact fallback;
privacy and terms remain visibly labelled drafts pending owner review.

The existing Vinext/Vite stack and independent public/product root documents
are retained. Explicit locale directories prevent generic public parameters
from shadowing product catch-all routes in the pinned router. Product providers,
Auth implementations, `/api/auth/**` and `/v1/**` handlers remain unchanged.

## Local preview and synthetic acceptance

Use the existing install instructions; no new package or lockfile change is
required. Run from the repository root:

```sh
COREPACK_HOME=/workspace/.cache/corepack corepack pnpm dev
# Or the supported Nitro development target:
node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5195
```

Open `/zh-HK` or `/en` on the local server. Public browsing needs no account or
identity-provider setting. Real intake is disabled by default. The API responds
503 without opening SQL when configuration is disabled or incomplete.

The independent synthetic fixture, secure handoff, readback and ownership-checked
cleanup commands are documented in
[`features/marketing/intake/README.md`](../../features/marketing/intake/README.md).
Browser acceptance uses `playwright.marketing-site.config.ts` and
`playwright.marketing-intake.config.ts`. Set `MARKETING_CHROMIUM` to an installed
Chromium executable where the default Playwright browser is unavailable. Do not
reuse an unrelated database or infer isolation from a loopback address.

The form accepts input only after hydration, validates on both boundaries,
uses a server challenge and durable rate limits, retains entries on errors,
and acknowledges only a committed receipt. An unchanged intent keeps its
idempotency key across retry; reload restores the receipt. Session storage holds
only receipt identifiers and a hash/key, never the submitted name/email/message.
Browser events are local `buyeros:marketing` CustomEvents only; no analytics
provider, cookies or remote transmission is installed.

## Public values required before publication

Enter these **non-secret** values in `config/marketing.public.json`:

| Field | Exact value needed |
| --- | --- |
| `siteUrl` | Final canonical HTTPS origin, e.g. `https://your-approved-domain`, no path/query/credentials |
| `legalEntity` | Approved legal publisher/data-controller name |
| `contactEmail` | Approved public privacy/contact email address |
| `leadRetentionDays` | Approved intake retention period, integer1–365days |
| `privacyApproved` | `true` only after the final privacy text and data handling are approved |
| `termsApproved` | `true` only after the final terms are approved |

Review and edit both legal page texts in
`features/marketing/content.ts` (`siteCopy['zh-HK'].pages.privacy/terms` and
`siteCopy.en.pages.privacy/terms`) with the approved policies. Do not merely
change the booleans to remove draft labels. `MARKETING_SITE_URL` is an optional
server-only canonical-origin override for a local/staging process. Preview
responses remain noindex and the sitemap is empty until the domain and legal
configuration are approved. No invented Organization, offers, ratings or
customer outcomes are emitted. The FAQ JSON-LD uses the same visible answers.

## Separate approval and secure settings for real intake

No identity provider, model key, paid access or account is required to finish
this local marketing implementation. Real intake, deployment and real product
integration remain separate work. To activate real collection later, the owner
must approve the controller, lawful handling/consent text, retention, restricted
DB provisioning/migration, operational deletion and a target deployment.

Enter secret values only in the selected Node/API hosting environment's secure
server-variable controls or secret manager; never in chat, the public JSON,
client-prefixed variables or source control. Use the same exact approved public
origin on both boundaries. The full variable mapping and role grants are in the
intake README. Required values are:

- Node: `MARKETING_API_ORIGIN`, `MARKETING_PUBLIC_ORIGIN`,
  `MARKETING_GATEWAY_KEY` (generated secret, at least32ASCII characters).
- API: `BUYEROS_MARKETING_PUBLIC_ORIGIN`,
  `BUYEROS_MARKETING_GATEWAY_KEY` (same secret),
  `BUYEROS_MARKETING_DATABASE_URL` (dedicated intake PostgreSQL DSN using a
  restricted non-owner login), `BUYEROS_MARKETING_RETENTION_DAYS` (1–365).
- After explicit real-intake approval: Node `MARKETING_ENABLED=1`,
  `MARKETING_SYNTHETIC_MODE=0`, `MARKETING_REAL_INTAKE_APPROVED=1`; API equivalents
  `BUYEROS_MARKETING_ENABLED=1`, `BUYEROS_MARKETING_SYNTHETIC_MODE=0`,
  `BUYEROS_MARKETING_REAL_INTAKE_APPROVED=1`.

Apply the independent intake migration only to an approved dedicated target,
then provision the restricted runtime role. Tenant Alembic history is untouched.
Expiry cleanup currently runs on successful intake activity. A scheduled
retention/deletion job with monitoring and an approved interval is required
before claiming deletion during inactivity. There is no recipient-email sender
or outreach integration in this subsystem.

## Content, claims and assets

Canonical runtime copy: `features/marketing/content.ts`; generated reviewer
copy: [marketing-site-copy.md](marketing-site-copy.md). `public/marketing` holds
six actual product-demo screenshots populated with synthetic browser-local
fixtures and two original typographic OG images. Capture commands:

```sh
# No other frontend server on port5195; no real environment bindings.
node scripts/capture-marketing-assets.mjs
```

The capture script refuses API/provider requests and produces a hash receipt in
`outputs/marketing-full/capture-receipts.json`. Illustrations and captures are
visibly labelled synthetic; sources are not real research and drafts are unsent.

| Public claim | Implementation/evidence boundary |
| --- | --- |
| Buyer criteria and versioned profiles | Existing offer/profile UI and `services/api/buyeros_api` profile routes; no real provider acceptance inferred |
| Company/source review | Existing buyer/evidence UI; observations and inference distinguished; human review required |
| Saved outreach drafts | Existing draft editor/revision flow; fixed-template sample, no sending offered |
| CSV/XLSX imports | Existing import parser;500-row limit, no invented unlimited import |
| PDF/PPTX/TXT/MD product documents | Existing document intake; no DOCX promise |
| zh-HK and English UI | Actual localized public routes and product locale support; no claim of arbitrary translation |
| Configured research/providers | Conditional on service configuration and permission; this phase uses synthetic data only |
| Roles/workspace access | Existing product boundaries; no anonymous tenant access added |
| Pricing/private policies | Contact fallback and visible legal drafts until approved; no invented tiers/jurisdiction |

The original C01–C09 research mapping remains in
`outputs/marketing-plan.M4lEBk/claims-and-gaps.md`. No live AISO page was obtained
(the historical requests were denied before origin), and no AISO score or
customer result is claimed.

## Verification and revision

Final commands, results, fingerprints, local commit IDs and limitations are
recorded in [marketing-site-verification.md](marketing-site-verification.md) and
`outputs/marketing-full/verification.json`.
Historical core acceptance evidence and its seven-file uncommitted patch are
preserved separately. No push, merge, deployment or production data change is
part of this delivery.
