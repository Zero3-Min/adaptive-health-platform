"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

const FEATURES = [
  { icon: "🧠", text: "五层记忆——每条建议都引用你自己的数据" },
  { icon: "🔁", text: "教练 + 复盘双 Agent，越用越懂你" },
  { icon: "🧬", text: "会自我进化：系统自动优化自己的教练规则" },
];

/** 未设置 X-User-Id 时展示应用内注册/登录卡片。 */
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
    <div className="mx-auto mt-6 max-w-md">
      <div className="card p-8 shadow-sm">
        <div className="mb-1 text-3xl">🏃</div>
        <h1 className="text-lg font-semibold">开始你的健康操作系统</h1>
        <p className="mt-1 text-sm muted">
          输入邮箱创建账号——你的教练会随着每天的打卡越来越懂你。
        </p>
        <ul className="mt-4 space-y-1.5">
          {FEATURES.map((f) => (
            <li key={f.text} className="flex items-start gap-2 text-sm">
              <span>{f.icon}</span>
              <span className="muted">{f.text}</span>
            </li>
          ))}
        </ul>
        <form onSubmit={handleRegister} className="mt-5 space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="input"
          />
          <button type="submit" disabled={busy || !email.trim()} className="btn-primary w-full">
            {busy ? "创建中…" : "创建账号"}
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
        <div className="mt-6 border-t pt-4 divide-token" style={{ borderColor: "var(--border)" }}>
          <p className="mb-2 text-xs muted">已有用户 ID？直接粘贴：</p>
          <div className="flex gap-2">
            <input
              value={pasteId}
              onChange={(e) => setPasteId(e.target.value.trim())}
              placeholder="uuid"
              className="input font-mono text-xs"
              spellCheck={false}
            />
            <button onClick={() => pasteId && setUserId(pasteId)} disabled={!pasteId} className="btn-ghost">
              使用
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
