"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

interface ChatMessage {
  role: "user" | "coach";
  text: string;
  mocked?: boolean;
}

export default function CoachPage() {
  const { userId } = useUserId();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message) return;
    setError(null);
    if (!userId) {
      setError("请先在右上角填入 X-User-Id");
      return;
    }
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const { reply, mocked } = await api.coachChat(userId, message);
      setMessages((prev) => [...prev, { role: "coach", text: reply, mocked }]);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[70vh] flex-col">
      <h1 className="mb-4 text-xl font-semibold">教练对话</h1>
      <div className="flex-1 space-y-3 overflow-y-auto rounded-md border border-neutral-200 bg-white p-4">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">
            问点什么，比如：今天该练什么？
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "text-right" : "text-left"}>
            <div
              className={
                msg.role === "user"
                  ? "inline-block max-w-[80%] rounded-lg bg-neutral-900 px-3 py-2 text-sm text-white"
                  : "inline-block max-w-[80%] whitespace-pre-wrap rounded-lg bg-neutral-100 px-3 py-2 text-sm"
              }
            >
              {msg.text}
            </div>
            {msg.mocked && (
              <p className="mt-1 text-xs text-neutral-400">mock 模式（未配置 API Key）</p>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-neutral-400">教练思考中…</p>}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <form onSubmit={handleSend} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="今天该练什么？"
          className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          发送
        </button>
      </form>
    </div>
  );
}
