"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError, type DailyLogPayload } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

const today = () => new Date().toISOString().slice(0, 10);

export default function DailyLogPage() {
  const { userId } = useUserId();
  const [date, setDate] = useState(today());
  const [workout, setWorkout] = useState("");
  const [nutrition, setNutrition] = useState("");
  const [sleepHours, setSleepHours] = useState("");
  const [mood, setMood] = useState("");
  const [steps, setSteps] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    setError(null);
    if (!userId) {
      setError("请先在右上角填入 X-User-Id");
      return;
    }
    const payload: DailyLogPayload = { date };
    if (workout.trim()) payload.workout = { note: workout.trim() };
    if (nutrition.trim()) payload.nutrition = { note: nutrition.trim() };
    if (sleepHours !== "") payload.sleep_hours = Number(sleepHours);
    if (mood !== "") payload.mood = Number(mood);
    if (steps !== "") payload.steps = Number(steps);
    if (note.trim()) payload.recovery_note = note.trim();

    setBusy(true);
    try {
      await api.createLog(userId, payload);
      setStatus("已保存。同日重复提交会合并，不会清空已有数据。");
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
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">今日打卡</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={label}>日期</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} required />
        </div>
        <div>
          <label className={label}>训练</label>
          <input value={workout} onChange={(e) => setWorkout(e.target.value)} placeholder="如：晨跑 5km，配速 6:00" className={field} />
        </div>
        <div>
          <label className={label}>饮食</label>
          <input value={nutrition} onChange={(e) => setNutrition(e.target.value)} placeholder="如：三餐正常，蛋白质约 120g" className={field} />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={label}>睡眠（小时）</label>
            <input type="number" min={0} max={24} step={0.5} value={sleepHours} onChange={(e) => setSleepHours(e.target.value)} className={field} />
          </div>
          <div>
            <label className={label}>情绪（1-10）</label>
            <input type="number" min={1} max={10} value={mood} onChange={(e) => setMood(e.target.value)} className={field} />
          </div>
          <div>
            <label className={label}>步数</label>
            <input type="number" min={0} value={steps} onChange={(e) => setSteps(e.target.value)} className={field} />
          </div>
        </div>
        <div>
          <label className={label}>恢复备注</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="如：腿部轻微酸痛" className={field} />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {busy ? "提交中…" : "提交打卡"}
        </button>
      </form>
      {status && <p className="text-sm text-green-700">{status}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
