import type { Metadata } from "next";
import "./globals.css";
import { UserIdProvider } from "@/lib/user-id";
import { UserIdInput } from "@/components/user-id-input";
import { OnboardingGate } from "@/components/onboarding";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Health OS — Adaptive Health Platform",
  description: "A health OS that gets smarter every day",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <UserIdProvider>
          <header className="sticky top-0 z-10 border-b border-neutral-200 bg-white/90 backdrop-blur">
            <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
              <span className="font-semibold">🏃 Health OS</span>
              <Nav />
              <div className="ml-auto">
                <UserIdInput />
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-3xl px-4 py-8">
            <OnboardingGate>{children}</OnboardingGate>
          </main>
        </UserIdProvider>
      </body>
    </html>
  );
}
