import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { UserIdProvider } from "@/lib/user-id";
import { UserIdInput } from "@/components/user-id-input";

export const metadata: Metadata = {
  title: "Adaptive Health Platform",
  description: "Health OS MVP dashboard",
};

const NAV = [
  { href: "/", label: "今日打卡" },
  { href: "/coach", label: "教练对话" },
  { href: "/insights", label: "我的洞察" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <UserIdProvider>
          <header className="border-b border-neutral-200 bg-white">
            <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
              <span className="font-semibold">Health OS</span>
              <nav className="flex gap-4 text-sm text-neutral-600">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="hover:text-neutral-900"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <div className="ml-auto">
                <UserIdInput />
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
        </UserIdProvider>
      </body>
    </html>
  );
}
