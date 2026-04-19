import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RetailIQ — AI-Powered Superstore Site Intelligence",
  description:
    "Multi-agent AI platform that recommends optimal U.S. locations for new Target and Walmart superstores using agent-based market simulation, demographic intelligence, and real-time competitive analysis.",
  keywords: "retail site selection, AI market simulation, Walmart expansion, Target expansion, Phoenix retail",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
