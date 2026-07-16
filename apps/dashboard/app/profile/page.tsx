"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type ProfilePayload } from "@/lib/api";
import { useUserId } from "@/lib/user-id";

export default function ProfilePage() {
  const { userId } = useUserId();
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [goal, setGoal] = useState("");
  const [injuries, setInjuries] = useState("");
  const [avoid, setAvoid] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const profile = await api.getProfile(userId);
      setAge(profile.age?.toString() ?? "");
      setSex(profile.sex ?? "");
      setHeight(profile.height_cm?.toString() ?? "");
      setWeight(profile.weight_kg?.toString() ?? "");
      setGoal(profile.goal ?? "");
      const constraints = profile.constraints ?? {};
      setInjuries(Array.isArray(constraints.injuries) ? constraints.injuries.join("、") : "");
      setAvoid(Array.isArray(constraints.avoid) ? constraints.avoid.join("、") : "");
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
      }
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    setError(null);
    const payload: ProfilePayload = {};
    if (age !== "") payload.age = Number(age);
    if (sex.trim()) payload.sex = sex.trim();
    if (height !== "") payload.height_cm = Number(height);
    if (weight !== "") payload.weight_kg = Number(weight);
    if (goal.trim()) payload.goal = goal.trim();
    const constraints: Record<string, unknown> = {};
    const split = (s: string) => s.split(/[、,，;；]/).map((x) => x.trim()).filter(Boolean);
    if (injuries.trim()) constraints.injuries = split(injuries);
    if (avoid.trim()) constraints.avoid = split(avoid);
    if (Object.keys(constraints).length > 0) payload.constraints = constraints;

    setBusy(true);
    try {
      await api.updateProfile(userId, payload);
      setStatus("已保存 ✓ 教练从下一次对话起就会遵守这些约束。");
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
      <div>
        <h1 className="text-xl font-semibold">我的档案</h1>
        <p className="mt-1 text-sm text-neutral-500">
          目标决定建议的方向，健康限制是教练<strong>绝不会违背</strong>的红线。
        </p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-neutral-200 bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <label className={label}>年龄</label>
            <input type="number" min={1} max={149} value={age} onChange={(e) => setAge(e.target.value)} className={field} />
          </div>
          <div>
            <label className={label}>性别</label>
            <input value={sex} onChange={(e) => setSex(e.target.value)} placeholder="male / female" className={field} />
          </div>
          <div>
            <label className={label}>身高（cm）</label>
            <input type="number" min={1} step={0.5} value={height} onChange={(e) => setHeight(e.target.value)} className={field} />
          </div>
          <div>
            <label className={label}>体重（kg）</label>
            <input type="number" min={1} step={0.1} value={weight} onChange={(e) => setWeight(e.target.value)} className={field} />
          </div>
        </div>
        <div>
          <label className={label}>目标</label>
          <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="减脂 5kg / 备赛半马 / 改善睡眠" className={field} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={label}>伤病史（顿号分隔）</label>
            <input value={injuries} onChange={(e) => setInjuries(e.target.value)} placeholder="膝盖、下背" className={field} />
          </div>
          <div>
            <label className={label}>需要避免的动作（顿号分隔）</label>
            <input value={avoid} onChange={(e) => setAvoid(e.target.value)} placeholder="深蹲、跳跃" className={field} />
          </div>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {busy ? "保存中…" : "保存档案"}
        </button>
        {status && <p className="text-sm text-green-700">{status}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </div>
  );
}
