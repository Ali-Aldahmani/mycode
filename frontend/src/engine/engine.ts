/**
 * Engine client: owns the Pyodide worker and exposes the Runner and Checker
 * implementations. The worker starts loading as soon as the app opens.
 */
import * as Comlink from "comlink";
import { create } from "zustand";
import type { Trace, TableState } from "./frames";
import type { EngineWorkerApi } from "./worker/pyodide.worker";
import type {
  CheckResult,
  Checker,
  EngineStatus,
  Inputs,
  RunOptions,
  RunResult,
  Runner,
  ValueSpec,
} from "./types";

const RUN_TIMEOUT_MS = 10_000;

export const useEngineStatus = create<{ status: EngineStatus }>(() => ({
  status: { state: "idle" },
}));

const setStatus = (status: EngineStatus) => useEngineStatus.setState({ status });

let worker: Worker | null = null;
let remote: Comlink.Remote<EngineWorkerApi> | null = null;
let ready: Promise<void> | null = null;

function spawn(): Comlink.Remote<EngineWorkerApi> {
  worker = new Worker(new URL("./worker/pyodide.worker.ts", import.meta.url), { type: "module" });
  remote = Comlink.wrap<EngineWorkerApi>(worker);
  setStatus({ state: "loading", message: "Starting Python", progress: 0.02 });
  ready = remote
    .init(
      Comlink.proxy((message: string, progress: number) =>
        setStatus({ state: "loading", message, progress }),
      ),
    )
    .then((ms) => setStatus({ state: "ready", ms }))
    .catch((e: unknown) => {
      setStatus({ state: "error", message: e instanceof Error ? e.message : String(e) });
      throw e;
    });
  return remote;
}

/** Start loading Pyodide + pandas in the background (idempotent). */
export function startEngine(): Promise<void> {
  if (!remote) spawn();
  return ready!;
}

function restart() {
  worker?.terminate();
  worker = null;
  remote = null;
  spawn();
}

interface RawRunSuccess {
  ok: true;
  runId: string;
  frames: Trace["frames"];
  stages: Trace["stages"];
  visual: boolean;
  note?: string | null;
  output: TableState;
  result: ValueSpec;
  stdout: string;
  ms: number;
}
type RawRun = RawRunSuccess | { ok: false; runId: string; error: { type: string; message: string; line: number | null }; stdout: string; ms: number };

let seq = 0;
let latest = 0;
/** Python runs one call at a time; this chain keeps calls in order. */
let queue: Promise<unknown> = Promise.resolve();

class PyodideRunner implements Runner {
  readonly language = "python";

  run(code: string, inputs: Inputs, options: RunOptions = {}): Promise<RunResult> {
    const id = ++seq;
    if (options.latestOnly) latest = id;
    const runId = `run-${id}`;
    const job = queue.then(async (): Promise<RunResult> => {
      // A newer playground edit arrived while this one waited: skip it.
      if (options.latestOnly && id !== latest) return { ok: false, runId, stale: true };
      await startEngine();
      const call = remote!.run({
        runId,
        code,
        inputs,
        library: options.library,
        visualType: options.visualType,
        visual: options.visual,
      });
      let timer: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error("timeout")), RUN_TIMEOUT_MS);
      });
      let raw: RawRun;
      try {
        raw = (await Promise.race([call, timeout])) as RawRun;
      } catch {
        restart(); // the only way to stop a runaway Python loop
        return {
          ok: false,
          runId,
          error: { type: "Timeout", message: `Your code ran for more than ${RUN_TIMEOUT_MS / 1000}s and was stopped.`, line: null },
          stdout: "",
          ms: RUN_TIMEOUT_MS,
        };
      } finally {
        clearTimeout(timer);
      }
      if (options.latestOnly && id !== latest) return { ok: false, runId, stale: true };
      if (!raw.ok) return raw;
      return {
        ok: true,
        runId: raw.runId,
        trace: { frames: raw.frames, stages: raw.stages, visual: raw.visual, note: raw.note },
        output: raw.output,
        result: raw.result,
        stdout: raw.stdout,
        ms: raw.ms,
      };
    });
    queue = job.catch(() => undefined);
    return job;
  }
}

class PandasChecker implements Checker {
  readonly type = "pandas_equal";

  check(runId: string, target: ValueSpec, options?: Record<string, unknown>): Promise<CheckResult> {
    const job = queue.then(async () => {
      await startEngine();
      return (await remote!.check({ runId, target, options })) as CheckResult;
    });
    queue = job.catch(() => undefined);
    return job;
  }
}

const runners: Record<string, Runner> = { python: new PyodideRunner() };
const checkers: Record<string, Checker> = { pandas_equal: new PandasChecker() };

export function getRunner(language = "python"): Runner {
  const r = runners[language];
  if (!r) throw new Error(`No runner for language ${language}`);
  return r;
}

export function getChecker(type = "pandas_equal"): Checker {
  const c = checkers[type];
  if (!c) throw new Error(`No checker of type ${type}`);
  return c;
}
