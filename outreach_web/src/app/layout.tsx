import {ClerkProvider} from "@clerk/nextjs";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import AuthLayout from "@/components/AuthLayout";
import AuthProvider from "@/components/AuthProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Outreach Campaign Manager",
  description: "Simple premium campaign outreach app",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased text-base`}
    >
      <body className="min-h-full flex bg-slate-50/30 text-slate-900">
        <ClerkProvider>
          <AuthProvider>
            <AuthLayout>{children}</AuthLayout>
          </AuthProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}