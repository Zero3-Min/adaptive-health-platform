"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type EvolutionLog } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

/**
 * 进化史（Layer 5）——系统自我修改的可审计时间线。
 * 这是本产品最核心的差异点：教练不是静态的，它会自己提炼洞察、调整策略、
 * 采纳新规则，每一步都在这里留痕。
 */

interface ChangeMeta {
  icon: string;
  label: string;
  color: string;
}

const CHANGE_META: Record<string, ChangeMeta> = {
  strategy_replaced: { icon: "♻️", label: "策略替换", color: "#eda100" },
  strategy_adjusted_by_reflection: { icon: "🔧", label: "反思调整策略", color: "#eda100" },
  coach_rule_adopted: { icon: "🧠", label: "教练规则采纳", color: "#008300" },
  reflection_rule_adopted: { icon: "🧠", label: "反思规则采纳", color: "#008300" },
  embedding_degraded: { icon: "⚠️", label: "记忆检索降级", color: "#eb6834" },
};

function metaFor(changeType: string): ChangeMeta {
  return CHANGE_META[changeType] ?? { icon: "🧬", label: changeType, color: "#2a78d6" };
}

function scoreDelta(log: EvolutionLog): string | null {
  const before = log.before?.total;
  const after = log.after?.total;
  if (typeof before === "number" && typeof after === "number") {
    const arrow = after >= before ? "↑" : "↓";
    return `${before.toFixed(3)} → ${after.toFixed(3)} ${arrow}`;
  }
  return null;
}

function whatChanged(log: EvolutionLog): string | null {
  const rule = log.after?.rule;
  if (typeof rule === "string") return `采纳规则：${rule}`;
  const bc = log.before?.content;
  const ac = log.after?.content;
  if (typeof ac === "string") {
    return typeof bc === "string" ? `「${bc}」→「${ac}」` : `新策略：${ac}`;
  }
  return null;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function EvolutionPage() {
  const { userId } = useUserId();
  const [logs, setLogs] = useState<EvolutionLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      setLogs(await api.listEvolution(userId));
      setLoaded(true);
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  const adoptions = logs.filter((l) => l.change_type.endsWith("rule_adopted")).length;
  const strategyChanges = logs.filter((l) => l.change_type.includes("strategy")).length;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">🧬 进化史</h1>
        <p className="mt-1 text-sm muted">
          这套系统不是静态的教练——它会分析你的数据、提炼洞察、调整策略，甚至
          <strong>重写自己的提示词规则</strong>。下面是它每一次自我修改的完整、可审计的记录。
        </p>
      </div>

      {loaded && logs.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { n: logs.length, label: "总演进事件" },
            { n: adoptions, label: "自采纳规则" },
            { n: strategyChanges, label: "策略调整" },
          ].map((s) => (
            <div key={s.label} className="card p-4 text-center">
              <div className="text-2xl font-bold" style={{ color: "var(--accent)" }}>
                {s.n}
              </div>
              <div className="mt-1 text-xs muted">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      {loaded && logs.length === 0 && (
        <div className="card border-dashed p-8 text-center">
          <p className="text-2xl">🧬</p>
          <p className="mt-2 text-sm muted">
            还没有演进记录。去打卡几天、运行一次反思，系统就会开始自我进化。
          </p>
        </div>
      )}

      <ol className="relative space-y-4 border-l pl-6 divide-token" style={{ borderColor: "var(--border)" }}>
        {logs.map((log) => {
          const meta = metaFor(log.change_type);
          const delta = scoreDelta(log);
          const changed = whatChanged(log);
          return (
            <li key={log.id} className="relative">
              <span
                className="absolute -left-[31px] flex h-6 w-6 items-center justify-center rounded-full text-xs"
                style={{ background: "var(--surface)", border: `2px solid ${meta.color}` }}
              >
                {meta.icon}
              </span>
              <div className="card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                    style={{ background: `${meta.color}22`, color: meta.color }}
                  >
                    {meta.label}
                  </span>
                  {delta && (
                    <span className="rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
                      style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                      {delta}
                    </span>
                  )}
                  <span className="ml-auto text-xs muted">{timeAgo(log.created_at)}</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed">{log.reason}</p>
                {changed && (
                  <p className="mt-2 rounded-md p-2 text-xs surface-2 muted">{changed}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
