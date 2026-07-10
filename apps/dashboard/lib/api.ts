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

export const api = {
  createLog: (userId: string, payload: DailyLogPayload) =>
    request<DailyLogPayload>("/logs", userId, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
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
};
