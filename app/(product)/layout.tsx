import type { Metadata } from "next";
import "../globals.css";
import { DataModeProvider } from "@/features/providers/data-mode";
import { WorkspaceSessionProvider } from "@/features/providers/workspace-session";
import { resolveMode } from "@/services/live/mode";

import {loadPublicAuth} from "@/lib/auth/public-auth";

export const metadata: Metadata = {
  title: "FIMMICK BuyerOS",
  description: "Buyer discovery, evidence review and human-approved outreach. Private demo workspace.",
  robots: { index: false, follow: false },
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const apiBaseUrl = process.env.BUYEROS_API_BASE_URL ?? '';
  // Use the tested resolver rather than re-deriving the rule inline.
  const mode = resolveMode(apiBaseUrl);
  return (
    <html lang="en">
      <body className="antialiased">
        <DataModeProvider mode={mode} apiBaseUrl={apiBaseUrl}>
          <WorkspaceSessionProvider publicAuth={loadPublicAuth({
            ...process.env,
            // Vite injects these public Neon settings into the separate Cloudflare RSC runtime.
            // The cookie secret stays a runtime server value and is not part of that public define list.
            BUYEROS_AUTH_PROVIDER: process.env.BUYEROS_AUTH_PROVIDER,
            BUYEROS_NEON_AUTH_ROUTE_ENABLED: process.env.BUYEROS_NEON_AUTH_ROUTE_ENABLED,
            BUYEROS_NEON_ENVIRONMENT: process.env.BUYEROS_NEON_ENVIRONMENT,
            BUYEROS_NEON_AUTH_URL: process.env.BUYEROS_NEON_AUTH_URL,
            BUYEROS_NEON_EXPECTED_AUTH_URL: process.env.BUYEROS_NEON_EXPECTED_AUTH_URL,
            BUYEROS_PUBLIC_ORIGIN: process.env.BUYEROS_PUBLIC_ORIGIN,
            BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN: process.env.BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN,
            // Narrow deployment-bound QA preview allowlist. VERCEL_* values are
            // platform-injected deployment facts, never request/host guesses. On
            // the Vercel target these reads stay in the server bundle and resolve
            // at request time, so the auth decision uses the current deployment.
            BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED: process.env.BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED,
            BUYEROS_QA_PREVIEW_PROJECT_ID: process.env.BUYEROS_QA_PREVIEW_PROJECT_ID,
            BUYEROS_QA_PREVIEW_TEAM_ID: process.env.BUYEROS_QA_PREVIEW_TEAM_ID,
            BUYEROS_QA_PREVIEW_REPO: process.env.BUYEROS_QA_PREVIEW_REPO,
            BUYEROS_QA_PREVIEW_REPO_ID: process.env.BUYEROS_QA_PREVIEW_REPO_ID,
            BUYEROS_QA_PREVIEW_BRANCH: process.env.BUYEROS_QA_PREVIEW_BRANCH,
            BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN: process.env.BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN,
            BUYEROS_RUNTIME_SOURCE_SHA: process.env.BUYEROS_RUNTIME_SOURCE_SHA,
            VERCEL_ENV: process.env.VERCEL_ENV,
            VERCEL_URL: process.env.VERCEL_URL,
            VERCEL_PROJECT_ID: process.env.VERCEL_PROJECT_ID,
            VERCEL_TEAM_ID: process.env.VERCEL_TEAM_ID,
            VERCEL_GIT_PROVIDER: process.env.VERCEL_GIT_PROVIDER,
            VERCEL_GIT_REPO_OWNER: process.env.VERCEL_GIT_REPO_OWNER,
            VERCEL_GIT_REPO_SLUG: process.env.VERCEL_GIT_REPO_SLUG,
            VERCEL_GIT_REPO_ID: process.env.VERCEL_GIT_REPO_ID,
            VERCEL_GIT_COMMIT_REF: process.env.VERCEL_GIT_COMMIT_REF,
            VERCEL_GIT_COMMIT_SHA: process.env.VERCEL_GIT_COMMIT_SHA,
            BUYEROS_NEON_COOKIE_SECRET: process.env.BUYEROS_NEON_COOKIE_SECRET,
          })}>
            {children}
          </WorkspaceSessionProvider>
        </DataModeProvider>
      </body>
    </html>
  );
}
