"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Insight, type Strategy } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

export default function InsightsPage() {
  const { userId } = useUserId();
  const [insights, setInsights] = useState<Insight[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      const [ins, strats] = await Promise.all([
        api.listInsights(userId),
        api.listStrategies(userId),
      ]);
      setInsights(ins);
      setStrategies(strats);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleReflect() {
    if (!userId) {
      setError("请先在右上角填入 X-User-Id");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.runReflection(userId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">我的洞察</h1>
        <button
          onClick={handleReflect}
          disabled={busy}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {busy ? "反思中…" : "运行今日反思"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!userId && (
        <p className="text-sm text-neutral-400">请先在右上角填入 X-User-Id。</p>
      )}

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Insights
        </h2>
        {loaded && insights.length === 0 && (
          <p className="text-sm text-neutral-400">暂无洞察。打卡几天后运行反思试试。</p>
        )}
        <ul className="space-y-2">
          {insights.map((insight) => (
            <li key={insight.id} className="rounded-md border border-neutral-200 bg-white p-3">
              <p className="text-sm">{insight.content}</p>
              <p className="mt-1 text-xs text-neutral-500">
                {insight.category} · 置信度 {insight.confidence.toFixed(2)} · 来源{" "}
                {insight.source}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          当前策略
        </h2>
        {loaded && strategies.length === 0 && (
          <p className="text-sm text-neutral-400">暂无生效策略。</p>
        )}
        <ul className="space-y-2">
          {strategies.map((strategy) => (
            <li key={strategy.id} className="rounded-md border border-neutral-200 bg-white p-3">
              <p className="text-sm">{strategy.content}</p>
              <p className="mt-1 text-xs text-neutral-500">{strategy.domain}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
