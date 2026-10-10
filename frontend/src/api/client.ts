import type {
  ChallengeDetail,
  ChallengeSummary,
  HelpKind,
  Progress,
  Submission,
  SubmissionIn,
  SubmissionResult,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Can't reach the API. Is the backend running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  challenges: () => request<ChallengeSummary[]>("/challenges"),
  challenge: (slug: string, includeSolution = false) =>
    request<ChallengeDetail>(`/challenges/${slug}${includeSolution ? "?include_solution=true" : ""}`),
  submissions: (slug: string) => request<Submission[]>(`/challenges/${slug}/submissions`),
  progress: () => request<Progress>("/progress"),
  submit: (body: SubmissionIn) => request<SubmissionResult>("/submissions", { method: "POST", body: JSON.stringify(body) }),
  openHelp: (slug: string, kind: HelpKind) =>
    request<{ help_used: HelpKind[]; cost: number }>(`/progress/${slug}/help`, { method: "POST", body: JSON.stringify({ kind }) }),
};
