"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

interface ChatMessage {
  role: "user" | "coach";
  text: string;
  mocked?: boolean;
}

const SUGGESTIONS = ["今天该练什么？", "我最近睡得不好，训练要调整吗？", "帮我看看这周的状态", "减脂平台期怎么破？"];

export default function CoachPage() {
  const { userId } = useUserId();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setError(null);
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

  function handleSend(event: FormEvent) {
    event.preventDefault();
    void send(input.trim());
  }

  return (
    <div className="flex h-[72vh] flex-col">
      <div className="mb-4">
        <h1 className="text-xl font-semibold">教练对话</h1>
        <p className="mt-1 text-sm muted">
          教练读得到你的档案、近 7 天记录、历史洞察和当前策略。
        </p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto card p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <span className="text-3xl">💬</span>
            <p className="text-sm muted">试试这些问题：</p>
            <div className="flex max-w-md flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => void send(s)}
                  className="btn-ghost rounded-full text-xs"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "text-right" : "text-left"}>
            <div
              className={
                msg.role === "user"
                  ? "inline-block max-w-[80%] rounded-2xl rounded-br-sm px-4 py-2 text-sm text-white [background:var(--accent)]"
                  : "inline-block max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-bl-sm surface-2 px-4 py-2 text-sm leading-relaxed"
              }
            >
              {msg.text}
            </div>
            {msg.mocked && (
              <p className="mt-1 text-xs muted">mock 模式（未配置 LLM key）</p>
            )}
          </div>
        ))}
        {busy && (
          <div className="text-left">
            <div className="inline-block rounded-2xl rounded-bl-sm surface-2 px-4 py-2 text-sm muted">
              教练思考中<span className="animate-pulse">…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <form onSubmit={handleSend} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="问点什么…"
          className="input flex-1 rounded-full"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="btn-primary rounded-full"
        >
          发送
        </button>
      </form>
    </div>
  );
}
