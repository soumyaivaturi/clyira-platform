import type { Metadata } from "next";
import { Inter, Orbitron } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });
const orbitron = Orbitron({
  subsets: ["latin"],
  weight: ["700", "900"],
  variable: "--font-brand",
});

export const metadata: Metadata = {
  title: "Clyira — Quality Intelligence Platform",
  description:
    "AI-powered regulatory compliance and audit readiness for life sciences",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} ${orbitron.variable}`}>
        <div className="min-h-screen flex flex-col">{children}</div>
      </body>
    </html>
  );
}
