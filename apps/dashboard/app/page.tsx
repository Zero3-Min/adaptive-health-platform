"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type DailyLog, type DailyLogPayload } from "@/lib/api";
import { useUserId } from "@/lib/user-id";
import { TrendCharts } from "@/components/trend-chart";

const today = () => new Date().toISOString().slice(0, 10);

const MOOD_EMOJI: Record<number, string> = {
  1: "😖", 2: "😞", 3: "😕", 4: "🙁", 5: "😐",
  6: "🙂", 7: "😊", 8: "😄", 9: "😁", 10: "🤩",
};

export default function DailyLogPage() {
  const { userId } = useUserId();
  const [date, setDate] = useState(today());
  const [workout, setWorkout] = useState("");
  const [nutrition, setNutrition] = useState("");
  const [sleepHours, setSleepHours] = useState("");
  const [mood, setMood] = useState<number | null>(null);
  const [steps, setSteps] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<DailyLog[]>([]);

  const loadLogs = useCallback(async () => {
    if (!userId) return;
    try {
      setLogs(await api.getLogs(userId, 7));
    } catch {
      /* 趋势区为增强信息，加载失败不阻塞打卡 */
    }
  }, [userId]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    setError(null);
    const payload: DailyLogPayload = { date };
    if (workout.trim()) payload.workout = { note: workout.trim() };
    if (nutrition.trim()) payload.nutrition = { note: nutrition.trim() };
    if (sleepHours !== "") payload.sleep_hours = Number(sleepHours);
    if (mood !== null) payload.mood = mood;
    if (steps !== "") payload.steps = Number(steps);
    if (note.trim()) payload.recovery_note = note.trim();

    setBusy(true);
    try {
      await api.createLog(userId, payload);
      setStatus("已保存 ✓ 同日重复提交会合并，不会清空已有数据。");
      await loadLogs();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setBusy(false);
    }
  }

  const field =
    "w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none";
  const label = "mb-1 block text-sm font-medium text-neutral-700";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">今日打卡</h1>
        <p className="mt-1 text-sm text-neutral-500">
          记录越多，教练越懂你——每条建议都会引用你自己的数据。
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-neutral-200 bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>日期</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} required />
          </div>
          <div>
            <label className={label}>步数</label>
            <input type="number" min={0} value={steps} onChange={(e) => setSteps(e.target.value)} placeholder="8000" className={field} />
          </div>
        </div>
        <div>
          <label className={label}>今天的情绪</label>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(MOOD_EMOJI).map(([value, emoji]) => {
              const v = Number(value);
              const selected = mood === v;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMood(selected ? null : v)}
                  aria-label={`情绪 ${value} 分`}
                  className={
                    selected
                      ? "rounded-lg border-2 border-neutral-900 bg-neutral-100 px-2 py-1 text-lg"
                      : "rounded-lg border border-neutral-200 px-2 py-1 text-lg opacity-60 hover:opacity-100"
                  }
                >
                  {emoji}
                </button>
              );
            })}
            {mood !== null && <span className="self-center text-sm text-neutral-500">{mood}/10</span>}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>睡眠（小时）</label>
            <input type="number" min={0} max={24} step={0.5} value={sleepHours} onChange={(e) => setSleepHours(e.target.value)} placeholder="7.5" className={field} />
          </div>
          <div>
            <label className={label}>训练</label>
            <input value={workout} onChange={(e) => setWorkout(e.target.value)} placeholder="晨跑 5km，配速 6:00" className={field} />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>饮食</label>
            <input value={nutrition} onChange={(e) => setNutrition(e.target.value)} placeholder="三餐正常，蛋白质约 120g" className={field} />
          </div>
          <div>
            <label className={label}>恢复备注</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="腿部轻微酸痛" className={field} />
          </div>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {busy ? "提交中…" : "提交打卡"}
        </button>
        {status && <p className="text-sm text-green-700">{status}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      <TrendCharts logs={logs} />
    </div>
  );
}
