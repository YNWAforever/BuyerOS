import type { Metadata } from "next";
import "../globals.css";
import { DataModeProvider } from "@/features/providers/data-mode";
import { WorkspaceSessionProvider } from "@/features/providers/workspace-session";
import { resolveMode } from "@/services/live/mode";

import {loadPublicAuth} from "@/lib/auth/public-auth";

export const metadata: Metadata = {
  title: "FIMMICK BuyerOS",
  description: "Buyer discovery, evidence review and human-approved outreach. Private demo workspace.",
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
            // Vite injects these public settings into the separate Cloudflare RSC runtime.
            BUYEROS_AUTH0_ISSUER: process.env.BUYEROS_AUTH0_ISSUER,
            BUYEROS_AUTH0_CLIENT_ID: process.env.BUYEROS_AUTH0_CLIENT_ID,
            BUYEROS_AUTH0_AUDIENCE: process.env.BUYEROS_AUTH0_AUDIENCE,
          })}>
            {children}
          </WorkspaceSessionProvider>
        </DataModeProvider>
      </body>
    </html>
  );
}
