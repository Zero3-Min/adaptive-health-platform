"use client";

import { useUserId } from "@/lib/user-id";

export function UserIdInput() {
  const { userId, setUserId } = useUserId();
  if (!userId) return null;
  return (
    <button
      onClick={() => {
        if (confirm("退出当前账号？（会清除本地保存的 User ID）")) setUserId("");
      }}
      className="btn-ghost font-mono text-xs"
      title={`当前用户 ${userId}\n点击退出`}
    >
      {userId.slice(0, 8)}… ⏻
    </button>
  );
}
