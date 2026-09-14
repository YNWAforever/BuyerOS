import type { Metadata } from "next";
import "./globals.css";
import Workspace from "@/features/workspace";

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
  return (
    <html lang="en">
      <body className="antialiased"><Workspace /></body>
    </html>
  );
}
