# Login recovery and registration

Branch: `codex/auth-recovery-registration`
Production base inspected: `699739a3bfddc70f0eb52d9343d06ef091d1e214`.

The deployed sign-in page had no password recovery or registration path. Its adapter required a browser-local transaction before signing in, so a copied URL with a state query could not complete login in another browser.

## Changes

- Sign-in links to account creation and password recovery; unverified accounts can resend verification email.
- New routes: `/auth/sign-up`, `/auth/forgot-password`, `/auth/reset-password`, and `/auth/verify-email`, in English and Traditional Chinese.
- Use the existing installed Neon server SDK routes. No new identity store, mail provider, workspace grants, or provider configuration changes.
- Explicit login can create a fresh transaction when the previous browser-local transaction is missing or expired. Callback state validation remains strict and one-use; URL state is never adopted as trusted state.
- Verification emails return to a stable sign-in page rather than relying on another tab's temporary transaction.
- Reset tokens stay in form memory, are removed from the address bar/history, and use a no-referrer auth layout. Passwords and reset tokens are never persisted by these flows.
- Registration retains invitation-controlled workspace membership. Reset requests use neutral confirmation text.

## Verification, 2026-11-06

- TypeScript: `node node_modules/typescript/bin/tsc --noEmit` passed.
- ESLint on changed auth source and browser tests: passed, no warnings.
- `node scripts/run-vercel.mjs build`: passed after rerunning outside the Windows filesystem sandbox.
- 60 focused adapter/boundary/recovery tests passed (`neon-session`, `neon-auth-boundary`, `auth-recovery`).
- 30 existing session/navigation/security regression tests passed (`t21-session`, `audit-auth-render`, `job-poller-checks`, `neon-security-proxy`).
- 4 installed-SDK tests passed for signup, reset request, password reset, and verification resend; all four also reject foreign origins.
- 5 new built-app browser tests passed: copied links, recovery requests, registration/verification, reset token/error handling, and mobile Traditional Chinese/rate limits.
- 9 existing built-app login/session/security browser tests passed.
- CI includes the new adapter, SDK, and browser suites. These local runs are focused checks, not a claim of full hosted CI completion.

Browser and SDK verification used synthetic accounts and intercepted transport. No real email was sent, account created, workspace granted, or production deployment performed. Real provider email delivery and a recipient's verification/reset round trip remain live acceptance checks.

## Release

Publish the scoped branch and review its PR, require hosted CI, then deploy through the existing production release process with authorization. Verify the live sign-in links and use an authorized test mailbox to complete registration, verification, password reset, and subsequent sign-in. A new authenticated user must still need an administrator's workspace invitation. Revert this change to roll back; there is no database migration.
