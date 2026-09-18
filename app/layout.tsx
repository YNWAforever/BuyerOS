import type { Metadata } from "next";
import "./globals.css";
import Workspace from "@/features/workspace";
import { DataModeProvider } from "@/features/providers/data-mode";
import { WorkspaceSessionProvider } from "@/features/providers/workspace-session";
import { resolveMode } from "@/services/live/mode";

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
          <WorkspaceSessionProvider>
            <Workspace mode={mode} />
          </WorkspaceSessionProvider>
        </DataModeProvider>
      </body>
    </html>
  );
}
