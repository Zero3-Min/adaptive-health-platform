"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "今日打卡", icon: "📝" },
  { href: "/coach", label: "教练对话", icon: "💬" },
  { href: "/insights", label: "我的洞察", icon: "💡" },
  { href: "/profile", label: "我的档案", icon: "👤" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 text-sm">
      {NAV.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={
              active
                ? "rounded-md bg-neutral-900 px-3 py-1.5 font-medium text-white"
                : "rounded-md px-3 py-1.5 text-neutral-600 hover:bg-neutral-100"
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
