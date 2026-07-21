"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Insight, type Strategy } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

const CATEGORY_STYLE: Record<string, string> = {
  sleep: "bg-blue-50 text-blue-700",
  training: "bg-green-50 text-green-700",
  nutrition: "bg-amber-50 text-amber-700",
  mood: "bg-purple-50 text-purple-700",
  recovery: "bg-teal-50 text-teal-700",
  habit: "bg-neutral-100 text-neutral-600",
};

function CategoryBadge({ category }: { category: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_STYLE[category] ?? "bg-neutral-100 text-neutral-600"}`}
    >
      {category}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={`置信度 ${value.toFixed(2)}`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full surface-2">
        <span
          className="block h-full rounded-full [background:var(--accent)]"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </span>
      <span className="text-xs tabular-nums muted">{value.toFixed(2)}</span>
    </span>
  );
}

export default function InsightsPage() {
  const { userId } = useUserId();
  const [insights, setInsights] = useState<Insight[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [justRan, setJustRan] = useState(false);

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
    setBusy(true);
    setError(null);
    setJustRan(false);
    try {
      await api.runReflection(userId);
      await load();
      setJustRan(true);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">我的洞察</h1>
          <p className="mt-1 text-sm muted">
            反思 Agent 分析你的时间线，把发现写回记忆——下一次教练建议会用上它们。
          </p>
        </div>
        <button
          onClick={handleReflect}
          disabled={busy}
          className="shrink-0 btn-primary"
        >
          {busy ? "反思中…" : "✨ 运行今日反思"}
        </button>
      </div>
      {justRan && <p className="text-sm text-green-700">反思完成 ✓ 新洞察已写入记忆。</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide muted">
          Insights（Layer 3）
        </h2>
        {loaded && insights.length === 0 && (
          <div className="card border-dashed p-8 text-center">
            <p className="text-2xl">💡</p>
            <p className="mt-2 text-sm muted">
              暂无洞察。打卡几天后点右上角「运行今日反思」试试。
            </p>
          </div>
        )}
        <ul className="space-y-2">
          {insights.map((insight) => (
            <li key={insight.id} className="card p-4">
              <p className="text-sm leading-relaxed">{insight.content}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <CategoryBadge category={insight.category} />
                <ConfidenceBar value={insight.confidence} />
                <span className="text-xs muted">来源 {insight.source}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide muted">
          当前策略（Layer 4）
        </h2>
        {loaded && strategies.length === 0 && (
          <p className="text-sm muted">暂无生效策略。反思发现明确模式后会自动建立。</p>
        )}
        <ul className="grid gap-2 sm:grid-cols-2">
          {strategies.map((strategy) => (
            <li key={strategy.id} className="card p-4">
              <div className="mb-1 flex items-center gap-2">
                <CategoryBadge category={strategy.domain} />
                <span className="text-xs text-green-500">● 生效中</span>
              </div>
              <p className="text-sm">{strategy.content}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
