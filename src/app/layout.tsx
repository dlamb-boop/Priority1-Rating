import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EasyPost Freight Quotes",
  description: "Internal LTL and truckload rating desk for EasyPost.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
