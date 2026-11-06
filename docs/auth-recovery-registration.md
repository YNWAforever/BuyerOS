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

## Verification codes and live acceptance, 2026-11-07

PR #45 was deployed after hosted CI passed. Live testing confirmed new-account creation, actual verification and password-reset email delivery, successful password reset, rejection of the old password, and sign-in with the new password. The test account has no workspace membership. Email verification itself remains pending recipient code entry; the mailbox connector masks one-time codes.

Neon's shared email service only supports verification codes. An attempted switch to links was rejected without changing the configuration. With explicit approval, signup verification emails are now enabled; OTP mode and the existing optional-verification sign-in policy are unchanged.

The follow-up adds six-digit code entry and resend to `/auth/verify-email` and keeps unverified signups on that form even when Neon creates a session. It uses the installed SDK's `email-otp/verify-email` endpoint. Codes are cleared after requests and never persisted. Success directs the user to sign in; workspace access still requires an invitation.

Local validation: production build, TypeScript, scoped lint, 63 focused auth tests, 5 installed-SDK tests, 6 recovery browser tests, and 9 existing login/session browser tests passed. Browser tests use synthetic intercepted transport. Hosted CI and live code verification must pass before claiming complete end-to-end acceptance.

Rollback the follow-up through Git; disabling signup verification emails separately restores the prior provider configuration. No schema migration or mail-provider replacement is involved.

Publish the scoped branch and review its PR, require hosted CI, then deploy through the existing production release process with authorization. Verify the live sign-in links and use an authorized test mailbox to complete registration, verification, password reset, and subsequent sign-in. A new authenticated user must still need an administrator's workspace invitation. Revert this change to roll back; there is no database migration.
