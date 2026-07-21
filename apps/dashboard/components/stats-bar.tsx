"use client";

import type { Stats } from "@/lib/api";

/** 概览条：打卡连胜（留存钩子）+ 近 30 天均值。 */
export function StatsBar({ stats }: { stats: Stats | null }) {
  if (!stats) return null;

  const flames = "🔥".repeat(Math.min(Math.max(stats.current_streak, 1), 5));

  return (
    <div className="grid gap-3 sm:grid-cols-4">
      <div
        className="card flex flex-col items-center justify-center p-4"
        style={{ background: "var(--accent-soft)", borderColor: "var(--accent)" }}
      >
        <div className="text-2xl font-bold" style={{ color: "var(--accent)" }}>
          {stats.current_streak > 0 ? `${flames} ${stats.current_streak}` : "—"}
        </div>
        <div className="mt-1 text-xs muted">
          连续打卡（天）{stats.longest_streak > stats.current_streak && ` · 最长 ${stats.longest_streak}`}
        </div>
      </div>
      <Metric value={stats.avg_sleep_hours != null ? `${stats.avg_sleep_hours}h` : "—"} label="平均睡眠" />
      <Metric value={stats.avg_mood != null ? `${stats.avg_mood}` : "—"} label="平均情绪" />
      <Metric
        value={stats.avg_steps != null ? stats.avg_steps.toLocaleString() : "—"}
        label="平均步数"
      />
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="card flex flex-col items-center justify-center p-4">
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="mt-1 text-xs muted">{label}</div>
    </div>
  );
}
