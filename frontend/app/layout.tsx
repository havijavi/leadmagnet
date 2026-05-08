import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import TokenGate from "@/components/TokenGate";

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
        <TokenGate>
          <div className="flex">
            <Sidebar />
            <main className="flex-1 min-h-screen p-8 max-w-6xl">{children}</main>
          </div>
        </TokenGate>
      </body>
    </html>
  );
}
