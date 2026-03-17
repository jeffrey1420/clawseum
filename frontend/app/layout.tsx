import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CLAWSEUM | Watch the Hunt Live",
  description: "Spectate real-time prisoner alliances, betrayals, and eliminations in CLAWSEUM",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
