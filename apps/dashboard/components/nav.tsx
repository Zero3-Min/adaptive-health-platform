"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "今日打卡", icon: "📝" },
  { href: "/coach", label: "教练对话", icon: "💬" },
  { href: "/insights", label: "我的洞察", icon: "💡" },
  { href: "/evolution", label: "进化史", icon: "🧬" },
  { href: "/profile", label: "我的档案", icon: "👤" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 text-sm">
      {NAV.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-md px-2.5 py-1.5 transition-colors"
            style={
              active
                ? { background: "var(--accent)", color: "#fff", fontWeight: 500 }
                : { color: "var(--text-muted)" }
            }
          >
            <span className="mr-1">{item.icon}</span>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
