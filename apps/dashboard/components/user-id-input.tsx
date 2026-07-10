"use client";

import { useUserId } from "@/lib/user-id";

export function UserIdInput() {
  const { userId, setUserId } = useUserId();
  return (
    <input
      value={userId}
      onChange={(e) => setUserId(e.target.value.trim())}
      placeholder="X-User-Id（注册返回的 UUID）"
      className="w-72 rounded-md border border-neutral-300 px-2 py-1 font-mono text-xs focus:border-neutral-500 focus:outline-none"
      spellCheck={false}
    />
  );
}
