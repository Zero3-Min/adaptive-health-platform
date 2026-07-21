"use client";

import type { DailyLog } from "@/lib/api";

/**
 * 近 7 天趋势：三个小型单序列柱状图（睡眠 / 情绪 / 步数），各自独立刻度。
 * 遵循 dataviz 规范：单轴、细柱、4px 圆角柱顶锚定基线、柱间留隙、
 * 最新值直接标注（黄色对比度 WARN 的补救）、hover 原生 tooltip。
 * 调色板（已通过 validate_palette 六项检查）：#2a78d6 / #008300 / #eda100。
 */

interface Metric {
  key: "sleep_hours" | "mood" | "steps";
  label: string;
  color: string;
  max: number;
  format: (v: number) => string;
}

const METRICS: Metric[] = [
  { key: "sleep_hours", label: "睡眠（小时）", color: "#2a78d6", max: 12, format: (v) => `${v}h` },
  { key: "mood", label: "情绪（1-10）", color: "#008300", max: 10, format: (v) => `${v}` },
  {
    key: "steps",
    label: "步数",
    color: "#eda100",
    max: 0, // 0 = 按数据自适应
    format: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`),
  },
];

const W = 260;
const H = 72;
const GAP = 6;

function MiniBars({ metric, logs }: { metric: Metric; logs: DailyLog[] }) {
  const values = logs.map((log) => {
    const v = log[metric.key];
    return typeof v === "number" ? v : null;
  });
  const present = values.filter((v): v is number => v !== null);
  if (present.length === 0) return null;

  const max = metric.max > 0 ? metric.max : Math.max(...present) * 1.15;
  const barW = (W - GAP * (values.length - 1)) / values.length;
  const lastIdx = values.reduce<number>((acc, v, i) => (v !== null ? i : acc), -1);

  return (
    <div className="card p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-xs font-medium muted">{metric.label}</span>
        {lastIdx >= 0 && (
          <span className="text-sm font-semibold [color:var(--text)]">
            {metric.format(values[lastIdx] as number)}
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={metric.label}>
        {values.map((v, i) => {
          if (v === null) {
            return (
              <rect
                key={i}
                x={i * (barW + GAP)}
                y={H - 3}
                width={barW}
                height={2}
                rx={1}
                fill="var(--border)"
              />
            );
          }
          const h = Math.max((v / max) * (H - 14), 3);
          return (
            <g key={i}>
              <rect
                x={i * (barW + GAP)}
                y={H - h}
                width={barW}
                height={h}
                rx={4}
                fill={metric.color}
                opacity={i === lastIdx ? 1 : 0.55}
              >
                <title>{`${logs[i].date}: ${metric.format(v)}`}</title>
              </rect>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] muted">
        <span>{logs[0]?.date.slice(5)}</span>
        <span>{logs[logs.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  );
}

export function TrendCharts({ logs }: { logs: DailyLog[] }) {
  if (logs.length === 0) return null;
  return (
    <section>
      <h2 className="mb-3 text-sm font-medium uppercase tracking-wide muted">
        近 7 天趋势
      </h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {METRICS.map((metric) => (
          <MiniBars key={metric.key} metric={metric} logs={logs} />
        ))}
      </div>
    </section>
  );
}
