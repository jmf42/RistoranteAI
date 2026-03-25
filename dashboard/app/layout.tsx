import type { Metadata } from "next";
import { Bodoni_Moda, Manrope } from "next/font/google";

import "@/app/globals.css";
import { WorkspaceProvider } from "@/components/workspace-provider";

const displayFont = Bodoni_Moda({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap"
});

const bodyFont = Manrope({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Ristorante AI",
  description: "AI phone receptionist and reservation control room for restaurants."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body
        className={`${displayFont.variable} ${bodyFont.variable}`}
        data-scroll-behavior="smooth"
      >
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </body>
    </html>
  );
}
