/// <reference lib="webworker" />
/**
 * Pyodide web worker. All Python runs here, never on the UI thread.
 * Loads Pyodide + pandas, installs /pyengine, then answers run/check calls.
 */
import * as Comlink from "comlink";
import type { PyodideAPI } from "pyodide";

export const PYODIDE_VERSION = "314.0.7";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// Every .py file of the shared engine, bundled as text.
const sources = import.meta.glob("../../../../pyengine/*.py", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

type Progress = (message: string, progress: number) => void;

let pyodide: PyodideAPI | null = null;
let loading: Promise<number> | null = null;

async function load(onProgress?: Progress): Promise<number> {
  const started = performance.now();
  onProgress?.("Downloading Python runtime", 0.1);
  const mod = (await import(/* @vite-ignore */ `${INDEX_URL}pyodide.mjs`)) as {
    loadPyodide: (opts: { indexURL: string }) => Promise<PyodideAPI>;
  };
  const py = await mod.loadPyodide({ indexURL: INDEX_URL });
  onProgress?.("Loading pandas", 0.5);
  await py.loadPackage(["numpy", "pandas"]);
  onProgress?.("Starting the visual engine", 0.9);
  py.FS.mkdirTree("/engine/pyengine");
  for (const [path, text] of Object.entries(sources)) {
    const file = path.split("/").pop()!;
    py.FS.writeFile(`/engine/pyengine/${file}`, text);
  }
  py.runPython(`
import sys
sys.path.insert(0, "/engine")
import pyengine.runner as _runner
_runner.run_json('{"code": "result = 1", "inputs": {}}')
`);
  pyodide = py;
  onProgress?.("Ready", 1);
  return Math.round(performance.now() - started);
}

function ensure(onProgress?: Progress): Promise<number> {
  if (!loading) {
    loading = load(onProgress).catch((e) => {
      loading = null;
      throw e;
    });
  }
  return loading;
}

function call(fn: "run_json" | "check_json", payload: unknown): unknown {
  if (!pyodide) throw new Error("Python engine is not loaded");
  const runner = pyodide.pyimport("pyengine.runner");
  try {
    const out = runner[fn](JSON.stringify(payload)) as string;
    return JSON.parse(out);
  } finally {
    runner.destroy();
  }
}

const api = {
  async init(onProgress?: Progress): Promise<number> {
    return ensure(onProgress);
  },
  async run(payload: { runId: string; code: string; inputs: unknown; library?: string; visualType?: string; visual?: boolean }) {
    await ensure();
    return call("run_json", payload);
  },
  async check(payload: { runId: string; target: unknown; options?: unknown }) {
    await ensure();
    return call("check_json", payload);
  },
};

export type EngineWorkerApi = typeof api;

Comlink.expose(api);
