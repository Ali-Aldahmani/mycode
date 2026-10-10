/** Mirrors the backend response schemas (backend/app/<module>/schemas.py). */
import type { TableState } from "@/engine/frames";
import type { ValueSpec } from "@/engine/types";

export type HelpKind = "example" | "hint_1" | "hint_2";

export interface ChallengeSummary {
  id: number;
  slug: string;
  order: number;
  level: number;
  title: string;
  method: string;
  category: string;
  locked: boolean;
  solved: boolean;
  best_score: number | null;
}

export interface ChallengeExample {
  inputs: Record<string, ValueSpec>;
  code: string;
  note: string;
}

export interface ChallengeDetail {
  id: number;
  slug: string;
  order: number;
  level: number;
  title: string;
  method: string;
  category: string;
  language: string;
  library: string;
  source: string;
  task: string;
  inputs: Record<string, ValueSpec>;
  target: ValueSpec;
  starter_code: string;
  hint_1: string;
  hint_2: string;
  example: ChallengeExample;
  why: string;
  docs_url: string;
  checker_type: string;
  checker_options: Record<string, unknown>;
  visual_type: string;
  costs: Record<HelpKind, number>;
  locked: boolean;
  solved: boolean;
  best_score: number | null;
  submitted: boolean;
  prev_slug: string | null;
  next_slug: string | null;
  total: number;
  help_used: HelpKind[];
  potential: number;
  display: { inputs: TableState[]; target: TableState; example_inputs: TableState[] };
  reference_solution: string | null;
}

export type SubmissionStatus = "correct" | "wrong" | "error";

export interface Submission {
  id: number;
  challenge_id: number;
  code: string;
  status: SubmissionStatus;
  score: number | null;
  hints_used: HelpKind[];
  used_example: boolean;
  used_hint_1: boolean;
  used_hint_2: boolean;
  attempt_number: number | null;
  round: number;
  error: string | null;
  reason: string | null;
  runtime_ms: number | null;
  created_at: string;
}

export interface OverallProgress {
  solved: number;
  total: number;
  total_score: number;
  average: number | null;
}

export interface CategoryProgress {
  level: number;
  category: string;
  solved: number;
  total: number;
  average: number | null;
}

export interface Progress {
  overall: OverallProgress;
  categories: CategoryProgress[];
}

export interface SubmissionIn {
  challenge_slug: string;
  code: string;
  status: SubmissionStatus;
  used_example: boolean;
  used_hint_1: boolean;
  used_hint_2: boolean;
  error?: string | null;
  reason?: string | null;
  runtime_ms?: number | null;
}

export interface SubmissionResult {
  submission: Submission;
  progress: { challenge_id: number; best_score: number | null; solved: boolean; unlocked: boolean; help_used: HelpKind[] };
  overall: OverallProgress;
  potential: number;
  next_slug: string | null;
  unlocked_next: boolean;
}
