import "./globals.css";
import type { Metadata } from "next";
import AuthGate from "@/components/AuthGate";
import ChromeShell from "@/components/ChromeShell";

export const metadata: Metadata = {
  title: "LeadMagnet",
  description: "Self-hosted lead generation, qualification, and outreach.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthGate>
          <ChromeShell>{children}</ChromeShell>
        </AuthGate>
      </body>
    </html>
  );
}
