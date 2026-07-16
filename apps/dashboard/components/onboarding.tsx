"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

/** 未设置 X-User-Id 时展示应用内注册/登录卡片，替代 curl 注册流程。 */
export function OnboardingGate({ children }: { children: ReactNode }) {
  const { userId, setUserId } = useUserId();
  const [email, setEmail] = useState("");
  const [pasteId, setPasteId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (userId) return <>{children}</>;

  async function handleRegister(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const user = await api.register(email.trim());
      setUserId(user.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("该邮箱已注册过。如果你有之前的用户 ID，请在下方粘贴。");
      } else {
        setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-md">
      <div className="rounded-xl border border-neutral-200 bg-white p-8 shadow-sm">
        <div className="mb-1 text-2xl">🏃</div>
        <h1 className="text-lg font-semibold">开始你的健康操作系统</h1>
        <p className="mt-1 text-sm text-neutral-500">
          输入邮箱创建账号——你的教练会随着每天的打卡越来越懂你。
        </p>
        <form onSubmit={handleRegister} className="mt-5 space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !email.trim()}
            className="w-full rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {busy ? "创建中…" : "创建账号"}
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <div className="mt-6 border-t border-neutral-100 pt-4">
          <p className="mb-2 text-xs text-neutral-400">已有用户 ID？直接粘贴：</p>
          <div className="flex gap-2">
            <input
              value={pasteId}
              onChange={(e) => setPasteId(e.target.value.trim())}
              placeholder="uuid"
              className="flex-1 rounded-md border border-neutral-300 px-3 py-1.5 font-mono text-xs focus:border-neutral-500 focus:outline-none"
              spellCheck={false}
            />
            <button
              onClick={() => pasteId && setUserId(pasteId)}
              disabled={!pasteId}
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:bg-neutral-50 disabled:opacity-50"
            >
              使用
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
