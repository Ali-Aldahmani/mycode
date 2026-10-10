/**
 * Phase 1 prototype: hard-coded tables, sample operations, the real
 * Pyodide -> frames -> player pipeline. Kept as a dev page at /lab.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CodeEditor } from "@/components/CodeEditor";
import { EngineStatusPill } from "@/components/EngineStatus";
import { getRunner } from "@/engine/engine";
import type { RunError } from "@/engine/types";
import { createPlayer, currentFrame, usePlayer } from "@/engine/player/store";
import { VisualPlayer } from "@/engine/player/VisualPlayer";
import { inputsFor, SAMPLES, type Sample } from "./samples";

export default function EngineLab() {
  const store = useMemo(() => createPlayer(), []);
  const [sample, setSample] = useState<Sample>(SAMPLES[0]);
  const [code, setCode] = useState(SAMPLES[0].code);
  const [error, setError] = useState<RunError | null>(null);
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(false);
  const [stats, setStats] = useState<string>("");
  const highlight = usePlayer((s) => currentFrame(s)?.code ?? null, store);

  const run = useCallback(
    async (src: string, names: string[], opts: { keepPosition?: boolean; latestOnly?: boolean } = {}) => {
      setBusy(true);
      const t0 = performance.now();
      const res = await getRunner().run(src, inputsFor(names), { latestOnly: opts.latestOnly });
      setBusy(false);
      if ("stale" in res) return;
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setError(null);
      setStats(`${res.trace.frames.length} frames · python ${res.ms.toFixed(0)}ms · total ${(performance.now() - t0).toFixed(0)}ms`);
      store.getState().load(res.trace, { keepPosition: opts.keepPosition, autoplay: !opts.keepPosition });
    },
    [store],
  );

  const pick = (s: Sample) => {
    setSample(s);
    setCode(s.code);
    void run(s.code, s.inputs);
  };

  useEffect(() => {
    void run(SAMPLES[0].code, SAMPLES[0].inputs);
  }, [run]);

  // live mode: every edit re-runs (debounced) and the stage keeps its position
  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const onEdit = (v: string) => {
    setCode(v);
    if (!live) return;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => void run(v, sample.inputs, { keepPosition: true, latestOnly: true }), 100);
  };

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex items-center gap-4 border-b border-white/5 bg-panel px-5 py-3">
        <Link to="/" className="text-sm font-semibold text-neutral-200">
          Pandas Visual Trainer
        </Link>
        <span className="rounded bg-amber-400/10 px-2 py-0.5 text-xs text-amber-300">Engine lab</span>
        <div className="flex-1" />
        <EngineStatusPill />
      </header>

      <main className="grid flex-1 gap-4 p-4 lg:grid-cols-[minmax(340px,440px)_1fr]">
        <section className="flex flex-col gap-4">
          <div className="rounded-lg bg-panel p-3">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">Sample operations</h2>
            <div className="grid grid-cols-2 gap-1.5">
              {SAMPLES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => pick(s)}
                  className={`rounded-md border px-2.5 py-2 text-left transition-colors ${
                    s.id === sample.id ? "border-amber-400/50 bg-amber-400/10" : "border-white/5 bg-white/[0.03] hover:bg-white/[0.07]"
                  }`}
                >
                  <div className="text-sm font-medium text-neutral-100">{s.title}</div>
                  <div className="text-[11px] text-neutral-500">{s.primitive}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col overflow-hidden rounded-lg bg-panel">
            <div className="flex items-center gap-2 border-b border-white/5 px-3 py-2">
              <span className="text-xs text-neutral-500">inputs: {sample.inputs.join(", ")}</span>
              <div className="flex-1" />
              <label className="flex items-center gap-1.5 text-xs text-neutral-400">
                <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} className="accent-amber-400" />
                live
              </label>
              <button
                onClick={() => void run(code, sample.inputs)}
                className="rounded-md bg-emerald-600 px-3 py-1 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                disabled={busy}
              >
                Run
              </button>
            </div>
            <div className="h-44">
              <CodeEditor value={code} onChange={onEdit} highlight={highlight} errorLine={error?.line} onSubmit={() => void run(code, sample.inputs)} />
            </div>
            {error && (
              <div className="border-t border-red-500/20 bg-red-500/10 px-3 py-2 font-mono text-xs text-red-300">
                {error.type}: {error.message}
                {error.line ? ` (line ${error.line})` : ""}
              </div>
            )}
          </div>
          <p className="text-xs leading-relaxed text-neutral-500">
            Space plays/pauses, ←/→ step, R replays. Drag the speed slider to the right end for <em>instant</em>. Turn on
            <em> live</em> and edit the code: the stage re-runs on every keystroke and stays on the same frame.
          </p>
          {stats && <p className="font-mono text-[11px] text-neutral-600">{stats}</p>}
        </section>

        <section className="min-w-0 rounded-lg bg-panel p-4">
          <VisualPlayer
            store={store}
            keys
            empty={<div className="flex h-40 items-center justify-center text-sm text-neutral-500">Loading Python + pandas…</div>}
          />
        </section>
      </main>
    </div>
  );
}
