import type { TableState, Trace } from "./frames";

/** JSON form of a DataFrame / Series / scalar (see /pyengine/valuespec.py). */
export type ValueSpec =
  | {
      type: "dataframe";
      columns: (string | number | (string | number)[])[];
      data: unknown[][];
      index?: unknown[];
      index_name?: string | string[] | null;
      dtypes?: Record<string, string>;
      columns_name?: string | null;
    }
  | {
      type: "series";
      name?: string | number | null;
      data: unknown[];
      index?: unknown[];
      index_name?: string | string[] | null;
      dtype?: string;
    }
  | { type: "scalar"; value: unknown; tuple?: boolean };

export type Inputs = Record<string, ValueSpec>;

export interface RunError {
  type: string;
  message: string;
  line: number | null;
}

export interface RunOptions {
  /** Selects the frame generator (pyengine/runner.py GENERATORS). */
  library?: string;
  /** Fallback primitive when row identity can't be tracked. */
  visualType?: string;
  /** Set false to skip frame generation. */
  visual?: boolean;
  /** A newer `latestOnly` run makes this one stale (playground typing). */
  latestOnly?: boolean;
}

export type RunResult =
  | {
      ok: true;
      runId: string;
      trace: Trace;
      output: TableState;
      result: ValueSpec;
      stdout: string;
      ms: number;
    }
  | { ok: false; runId: string; error: RunError; stdout: string; ms: number }
  | { ok: false; runId: string; stale: true };

/** run(code, inputs) -> output | error. v1 implementation: Pyodide in a worker. */
export interface Runner {
  readonly language: string;
  run(code: string, inputs: Inputs, options?: RunOptions): Promise<RunResult>;
}

export interface CheckDiff {
  user: TableState;
  target: TableState;
  diff: TableState | null;
}

export interface CheckResult {
  passed: boolean;
  reason: string;
  diff: CheckDiff | null;
}

/** check(output, target, options) -> pass/fail + diff. v1: pandas comparison. */
export interface Checker {
  readonly type: string;
  check(runId: string, target: ValueSpec, options?: Record<string, unknown>): Promise<CheckResult>;
}

export type EngineStatus =
  | { state: "idle" }
  | { state: "loading"; message: string; progress: number }
  | { state: "ready"; ms: number }
  | { state: "error"; message: string };
