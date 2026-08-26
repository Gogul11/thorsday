import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentOS",
  description: "A small task dashboard for AgentOS.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-[#f7f7f5] text-[#1e1e1c] h-full min-h-full overflow-hidden">
        {children}
      </body>
    </html>
  );
}
