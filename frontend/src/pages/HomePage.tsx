import { Link } from "react-router-dom";
import { useChallenges, useProgress } from "@/api/hooks";
import type { ChallengeSummary } from "@/api/types";
import { EngineStatusPill } from "@/components/EngineStatus";
import { scoreColor } from "@/components/ui";

const LEVEL_NAMES: Record<number, string> = {
  1: "Look at data",
  2: "Pick data",
  3: "Change data",
  4: "Clean data",
  5: "Transform values",
  6: "Summarize",
  7: "Combine tables",
  8: "Reshape",
  9: "Over time",
};

function Tile({ c }: { c: ChallengeSummary }) {
  const body = (
    <div
      className={`group flex h-full items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
        c.locked
          ? "border-white/[0.03] bg-white/[0.01] text-neutral-600"
          : c.solved
            ? "border-emerald-500/20 bg-emerald-500/[0.04] hover:bg-emerald-500/[0.08]"
            : "border-amber-400/30 bg-amber-400/[0.05] hover:bg-amber-400/[0.1]"
      }`}
    >
      <span
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-xs ${
          c.locked ? "bg-white/[0.03]" : c.solved ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-400/20 text-amber-200"
        }`}
      >
        {c.locked ? "🔒" : c.solved ? "✓" : c.order}
      </span>
      <div className="min-w-0 flex-1">
        <div className={`truncate text-sm ${c.locked ? "" : "text-neutral-100"}`}>{c.title}</div>
        <div className="truncate font-mono text-[11px] text-neutral-500">{c.method}</div>
      </div>
      <span className={`font-mono text-sm ${scoreColor(c.best_score)}`}>{c.best_score ?? ""}</span>
    </div>
  );
  return c.locked ? <div title="Solve the previous challenge to unlock">{body}</div> : <Link to={`/c/${c.slug}`}>{body}</Link>;
}

export default function HomePage() {
  const { data: path, isLoading, error } = useChallenges();
  const { data: progress } = useProgress();
  const levels = new Map<number, ChallengeSummary[]>();
  for (const c of path ?? []) levels.set(c.level, [...(levels.get(c.level) ?? []), c]);
  const next = path?.find((c) => !c.locked && !c.solved) ?? path?.find((c) => !c.locked);
  const overall = progress?.overall;

  return (
    <div className="min-h-full">
      <header className="flex items-center gap-4 border-b border-white/5 bg-panel px-6 py-3">
        <img src="/favicon.svg" alt="" className="h-6 w-6" />
        <span className="text-sm font-semibold text-neutral-100">Pandas Visual Trainer</span>
        <div className="flex-1" />
        <Link to="/lab" className="text-xs text-neutral-500 hover:text-neutral-300">
          Engine lab
        </Link>
        <EngineStatusPill />
      </header>

      <main className="mx-auto max-w-5xl space-y-8 px-6 py-8">
        <section className="flex flex-wrap items-end gap-6">
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-white">Learn pandas by watching it work</h1>
            <p className="mt-1 text-sm text-neutral-400">
              49 challenges, easy to hard. Each one unlocks the next. Every answer is animated so you see what your code did.
            </p>
          </div>
          {overall && (
            <div className="flex gap-6 rounded-lg bg-panel px-5 py-3">
              <div>
                <div className="text-xs text-neutral-500">Solved</div>
                <div className="font-mono text-lg text-white">
                  {overall.solved}
                  <span className="text-neutral-500">/{overall.total}</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-neutral-500">Average</div>
                <div className={`font-mono text-lg ${scoreColor(overall.average)}`}>{overall.average ?? "–"}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-500">Total</div>
                <div className="font-mono text-lg text-white">{overall.total_score}</div>
              </div>
            </div>
          )}
          {next && (
            <Link to={`/c/${next.slug}`} className="rounded-md bg-amber-500 px-4 py-2 text-sm font-semibold text-black hover:bg-amber-400">
              {overall?.solved ? "Continue" : "Start"}: {next.title} →
            </Link>
          )}
        </section>

        {isLoading && <p className="text-sm text-neutral-500">Loading the path…</p>}
        {error && (
          <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
            {error.message} Start it with <code className="font-mono">docker compose up</code> (see README).
          </p>
        )}

        {[...levels.entries()].map(([level, items]) => {
          const cat = progress?.categories.find((x) => x.level === level);
          return (
            <section key={level}>
              <div className="mb-3 flex items-baseline gap-3">
                <h2 className="text-sm font-semibold text-neutral-200">
                  <span className="mr-2 font-mono text-neutral-500">L{level}</span>
                  {LEVEL_NAMES[level] ?? items[0].category}
                </h2>
                <span className="text-xs text-neutral-500">
                  {items[0].category} · {cat ? `${cat.solved}/${cat.total} solved` : ""}
                  {cat?.average != null ? ` · average ${cat.average}` : ""}
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((c) => (
                  <Tile key={c.slug} c={c} />
                ))}
              </div>
            </section>
          );
        })}
      </main>
    </div>
  );
}
