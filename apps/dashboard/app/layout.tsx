import type { Metadata } from "next";
import "./globals.css";
import { UserIdProvider } from "@/lib/user-id";
import { ThemeProvider, ThemeToggle } from "@/lib/theme";
import { UserIdInput } from "@/components/user-id-input";
import { OnboardingGate } from "@/components/onboarding";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Health OS — 会自我进化的健康操作系统",
  description: "A health OS that gets smarter every day — and optimizes itself.",
};

const themeInit = `(function(){try{var t=localStorage.getItem('health-platform-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-screen antialiased">
        <ThemeProvider>
          <UserIdProvider>
            <header
              className="sticky top-0 z-10 border-b backdrop-blur"
              style={{
                borderColor: "var(--border)",
                background: "color-mix(in srgb, var(--bg) 85%, transparent)",
              }}
            >
              <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
                <span className="font-semibold">🏃 Health OS</span>
                <Nav />
                <div className="ml-auto flex items-center gap-2">
                  <UserIdInput />
                  <ThemeToggle />
                </div>
              </div>
            </header>
            <main className="mx-auto max-w-4xl px-4 py-8">
              <OnboardingGate>{children}</OnboardingGate>
            </main>
          </UserIdProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
