import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";

import { Providers } from "@/app/providers";

import "./globals.css";

// Inter for UI text: IBM Plex Sans is legible but institutional, and its
// wider forms fight the density anchors. IBM Plex Mono stays for hashes,
// receipt ids and keys — monospace is doing real work there, not decoration.
// These expose the loaded families under their own variable names. globals.css
// composes them into --font-sans / --font-mono with the fallback stacks; using
// distinct names avoids next/font and :root both declaring the same custom
// property on <html>, where equal specificity makes the winner source-order
// dependent.
const sans = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Grace",
  description: "Cryptographic governance proof layer for AI agents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
