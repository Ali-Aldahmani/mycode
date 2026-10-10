import type { ChallengeDetail } from "@/api/types";
import { RichText } from "@/components/ui";
import { TableView } from "@/engine/player/VisualPlayer";

export function DescriptionTab({ ch }: { ch: ChallengeDetail }) {
  const names = Object.keys(ch.inputs);
  return (
    <div className="space-y-6 p-5">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-white/[0.06] px-2.5 py-0.5 text-neutral-300">
            Level {ch.level} · {ch.category}
          </span>
          <span className="rounded-full bg-amber-400/10 px-2.5 py-0.5 font-mono text-amber-200">{ch.method}</span>
          {ch.solved && <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-emerald-300">Solved · best {ch.best_score}</span>}
        </div>
        <h1 className="text-xl font-semibold text-white">
          {ch.order}. {ch.title}
        </h1>
      </div>

      <p className="text-[15px] leading-relaxed text-neutral-200">
        <RichText text={ch.task} />
      </p>

      <div className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3 text-sm leading-relaxed text-neutral-400">
        Assign your answer to a variable named <code className="font-mono text-amber-200">result</code>. Already loaded:{" "}
        {names.map((n, i) => (
          <span key={n}>
            <code className="font-mono text-sky-300">{n}</code>
            {i < names.length - 1 ? ", " : ""}
          </span>
        ))}
        , plus <code className="font-mono text-sky-300">pd</code> and <code className="font-mono text-sky-300">np</code>.
      </div>

      <a
        href={ch.docs_url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-2 rounded-md border border-sky-400/20 bg-sky-400/5 px-3 py-1.5 text-sm text-sky-300 hover:bg-sky-400/10"
      >
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 3h7v7M10 14 21 3M21 14v7H3V3h7" />
        </svg>
        pandas docs: {ch.method}
        <span className="text-xs text-sky-300/60">free</span>
      </a>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Input{names.length > 1 ? "s" : ""} <span className="font-normal normal-case text-neutral-600">(locked)</span>
        </h2>
        <div className="rounded-lg bg-black/20 p-3">
          <TableView tables={ch.display.inputs} />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">Target</h2>
        <div className="rounded-lg bg-black/20 p-3">
          <TableView tables={[{ ...ch.display.target, title: "" }]} />
        </div>
        {Boolean(ch.checker_options.check_row_order) && (
          <p className="mt-2 text-xs text-neutral-500">Row order matters for this challenge.</p>
        )}
      </section>
    </div>
  );
}
