const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  userId: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(userId ? { "X-User-Id": userId } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }
  return (await response.json()) as T;
}

export interface DailyLogPayload {
  date: string;
  workout?: Record<string, unknown>;
  nutrition?: Record<string, unknown>;
  sleep_hours?: number;
  mood?: number;
  steps?: number;
  recovery_note?: string;
}

export interface DailyLog extends DailyLogPayload {
  id: string;
  user_id: string;
}

export interface Profile {
  age: number | null;
  sex: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  goal: string | null;
  constraints: Record<string, unknown> | null;
}

export interface ProfilePayload {
  age?: number;
  sex?: string;
  height_cm?: number;
  weight_kg?: number;
  goal?: string;
  constraints?: Record<string, unknown>;
}

export interface Insight {
  id: string;
  content: string;
  category: string;
  confidence: number;
  source: string;
  created_at: string | null;
}

export interface Strategy {
  id: string;
  domain: string;
  content: string;
  active: boolean;
  created_at: string | null;
}

export interface CoachReply {
  reply: string;
  mocked: boolean;
}

export interface ReflectionResult {
  insights: Insight[];
  strategies: Strategy[];
  mocked: boolean;
}

export interface User {
  id: string;
  email: string;
}

export interface EvolutionLog {
  id: string;
  change_type: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string;
  created_at: string | null;
}

export interface Stats {
  current_streak: number;
  longest_streak: number;
  days_logged: number;
  window_days: number;
  avg_sleep_hours: number | null;
  avg_mood: number | null;
  avg_steps: number | null;
}

export const api = {
  register: (email: string) =>
    request<User>("/users", "", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  getProfile: (userId: string) => request<Profile>("/profile", userId),
  updateProfile: (userId: string, payload: ProfilePayload) =>
    request<Profile>("/profile", userId, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  createLog: (userId: string, payload: DailyLogPayload) =>
    request<DailyLog>("/logs", userId, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getLogs: (userId: string, days = 7) =>
    request<DailyLog[]>(`/logs?days=${days}`, userId),
  coachChat: (userId: string, message: string) =>
    request<CoachReply>("/coach/chat", userId, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  listInsights: (userId: string) => request<Insight[]>("/insights", userId),
  listStrategies: (userId: string) =>
    request<Strategy[]>("/strategies", userId),
  runReflection: (userId: string) =>
    request<ReflectionResult>("/reflection/run", userId, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  listEvolution: (userId: string) =>
    request<EvolutionLog[]>("/evolution", userId),
  getStats: (userId: string) => request<Stats>("/stats", userId),
};
