import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSolution } from "@/api/hooks";
import type { ChallengeDetail } from "@/api/types";
import { EngineStatusPill } from "@/components/EngineStatus";
import { Button, RichText } from "@/components/ui";
import { usePlayer } from "@/engine/player/store";
import { TableView, VisualPlayer } from "@/engine/player/VisualPlayer";
import { EditableInputs } from "./EditableInputs";
import type { ChallengeSession, Outcome } from "./useChallengeSession";

/** True once the animation has reached its last frame (stays true until the outcome changes). */
function useRevealAtEnd(session: ChallengeSession, outcome: Outcome) {
  const atEnd = usePlayer((s) => s.layouts.length > 0 && s.index === s.layouts.length - 1, session.player);
  const [revealed, setRevealed] = useState(false);
  useEffect(() => setRevealed(false), [outcome.kind === "checked" ? outcome.verdict : outcome]);
  useEffect(() => {
    if (atEnd) setRevealed(true);
  }, [atEnd]);
  return revealed;
}

function Panel({ title, children, tone }: { title: string; children: React.ReactNode; tone?: "bad" | "good" }) {
  return (
    <div className="min-w-0 flex-1 rounded-lg border border-white/5 bg-black/20 p-3">
      <div className={`mb-2 text-[10.5px] font-semibold uppercase tracking-wider ${tone === "bad" ? "text-red-300/80" : tone === "good" ? "text-emerald-300/80" : "text-neutral-500"}`}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Verdict({ ch, session, outcome, onWatchReference }: { ch: ChallengeDetail; session: ChallengeSession; outcome: Extract<Outcome, { kind: "checked" }>; onWatchReference: () => void }) {
  const { verdict, submission, saveError } = outcome;
  if (verdict.passed) {
    const score = submission?.submission.score;
    return (
      <div className="space-y-3 rounded-lg border border-emerald-500/25 bg-emerald-500/[0.07] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-lg font-semibold text-emerald-300">✓ Correct</span>
          <span className="font-mono text-lg text-white">{score != null ? `${score} pts` : saveError ? "" : "saving…"}</span>
          {submission && submission.progress.best_score != null && (
            <span className="text-sm text-neutral-400">best {submission.progress.best_score}</span>
          )}
          <div className="flex-1" />
          {ch.next_slug && (
            <Link to={`/c/${ch.next_slug}`}>
              <Button variant="success">Next challenge →</Button>
            </Link>
          )}
        </div>
        {ch.why && (
          <p className="text-sm leading-relaxed text-neutral-300">
            <span className="font-medium text-emerald-200">Why this works: </span>
            <RichText text={ch.why} />
          </p>
        )}
        {submission?.unlocked_next && <p className="text-xs text-emerald-300/80">Next challenge unlocked.</p>}
        {saveError && <p className="text-xs text-amber-300">Couldn't save to the server: {saveError}</p>}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-500/25 bg-red-500/[0.07] p-4">
        <span className="text-lg font-semibold text-red-300">✗ Not yet</span>
        <span className="text-sm text-neutral-300">{verdict.reason}</span>
        <div className="flex-1" />
        <Button variant="subtle" onClick={() => document.querySelector<HTMLTextAreaElement>(".monaco-editor textarea")?.focus()}>
          Retry
        </Button>
        <Button variant="subtle" onClick={onWatchReference}>
          ▶ Watch the reference solution
        </Button>
      </div>
      {submission && (
        <p className="text-xs text-neutral-500">
          Attempt {submission.submission.attempt_number}. A correct answer is now worth{" "}
          <span className="font-mono text-amber-300">{submission.potential}</span> points.
        </p>
      )}
      {saveError && <p className="text-xs text-amber-300">Couldn't save to the server: {saveError}</p>}
      {verdict.diff && (
        <div className="flex flex-col gap-3 xl:flex-row">
          <Panel title="Your result" tone="bad">
            <TableView tables={[{ ...verdict.diff.user, title: "" }]} />
          </Panel>
          <Panel title="Target" tone="good">
            <TableView tables={[{ ...verdict.diff.target, title: "" }]} />
          </Panel>
          {verdict.diff.diff && (
            <Panel title="Diff">
              <TableView tables={[{ ...verdict.diff.diff, title: "" }]} />
              <p className="mt-2 text-[11px] leading-relaxed text-neutral-500">
                <span className="text-red-300">pulsing</span> = wrong value · <span className="text-red-300/70">dashed</span> = missing · <span className="text-orange-300">orange</span> = extra
              </p>
            </Panel>
          )}
        </div>
      )}
      <ReferenceSolution ch={ch} session={session} />
    </div>
  );
}

function ReferenceSolution({ ch, session }: { ch: ChallengeDetail; session: ChallengeSession }) {
  const { data } = useSolution(ch.slug, true);
  if (!data) return null;
  return (
    <details className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-2 text-sm">
      <summary className="cursor-pointer text-neutral-400">Show the reference solution code</summary>
      <pre className="mt-2 overflow-x-auto rounded bg-black/30 px-3 py-2 font-mono text-xs text-neutral-200">{data}</pre>
      <Button size="sm" variant="ghost" className="mt-2" onClick={() => void session.replay(data, "Reference solution")}>
        ▶ Animate it
      </Button>
    </details>
  );
}

export function ResultPanel({ ch, session }: { ch: ChallengeDetail; session: ChallengeSession }) {
  const { outcome } = session;
  const revealed = useRevealAtEnd(session, outcome);
  const { data: solution, refetch } = useSolution(ch.slug, session.canPlayground);
  const [inputsVersion, setInputsVersion] = useState(0);

  const watchReference = async () => {
    const code = solution ?? (await refetch()).data;
    if (code) void session.replay(code, "Reference solution");
  };

  const showStage = outcome.kind === "checked" || outcome.kind === "replay" || outcome.kind === "playground";

  return (
    <div className="flex h-full flex-col bg-panel">
      <div className="flex h-10 shrink-0 items-center gap-3 border-b border-white/5 px-4">
        <span className="text-sm font-medium text-neutral-200">{session.playground ? "Playground" : "Result"}</span>
        {outcome.kind === "replay" && <span className="text-xs text-neutral-500">{outcome.label}</span>}
        <div className="flex-1" />
        {session.canPlayground ? (
          <label className="flex cursor-pointer items-center gap-2 text-xs text-neutral-400" title="Edit the inputs and code; the visual updates live. Not scored.">
            <span>Playground</span>
            <button
              role="switch"
              aria-checked={session.playground}
              onClick={() => session.setPlayground(!session.playground)}
              className={`relative h-5 w-9 rounded-full transition-colors ${session.playground ? "bg-amber-500" : "bg-white/15"}`}
            >
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${session.playground ? "left-[18px]" : "left-0.5"}`} />
            </button>
          </label>
        ) : (
          <span className="text-xs text-neutral-600" title="Submit once to unlock the playground">
            Playground unlocks after a submission
          </span>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {outcome.kind === "idle" && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-neutral-500">
            <p>
              Write your code, then press <span className="text-neutral-300">Submit</span>{" "}
              <kbd className="rounded bg-white/10 px-1.5 py-0.5 text-xs">Ctrl Enter</kbd>. Your code runs in the browser
              and the stage shows what it actually did.
            </p>
            <EngineStatusPill />
          </div>
        )}
        {outcome.kind === "running" && (
          <div className="flex h-full items-center justify-center gap-3 text-sm text-neutral-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent" /> Running…
            <EngineStatusPill />
          </div>
        )}
        {outcome.kind === "error" && (
          <div className="space-y-2 rounded-lg border border-red-500/25 bg-red-500/[0.07] p-4">
            <div className="font-mono text-sm text-red-300">
              {outcome.error.type}: {outcome.error.message}
              {outcome.error.line ? <span className="text-red-300/70"> (line {outcome.error.line})</span> : null}
            </div>
            <p className="text-xs text-neutral-400">Errors don't count as attempts. Fix the code and submit again.</p>
            {outcome.stdout && <pre className="rounded bg-black/30 p-2 font-mono text-xs text-neutral-300">{outcome.stdout}</pre>}
          </div>
        )}

        {session.playground && (
          <div className="space-y-2 rounded-lg border border-amber-400/15 bg-amber-400/[0.03] p-3">
            <div className="flex items-center gap-3 text-xs text-neutral-400">
              <span>Edit any cell or the code: the stage re-runs and stays on the same frame. Not scored.</span>
              <div className="flex-1" />
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  session.resetInputs();
                  setInputsVersion((v) => v + 1);
                }}
              >
                Reset inputs
              </Button>
            </div>
            <EditableInputs inputs={session.playInputs} onChange={session.setPlayInputs} version={inputsVersion} />
            {outcome.kind === "playground" && outcome.error && (
              <div className="font-mono text-xs text-red-300">
                {outcome.error.type}: {outcome.error.message}
              </div>
            )}
          </div>
        )}

        {showStage && <VisualPlayer store={session.player} keys />}

        {outcome.kind === "checked" && revealed && (
          <div ref={(el) => el?.scrollIntoView({ behavior: "smooth", block: "nearest" })}>
            <Verdict ch={ch} session={session} outcome={outcome} onWatchReference={() => void watchReference()} />
          </div>
        )}
        {outcome.kind === "checked" && !revealed && (
          <button className="text-xs text-neutral-500 underline-offset-2 hover:underline" onClick={() => session.player.getState().seek(1e9)}>
            Skip to the verdict
          </button>
        )}
        {outcome.kind === "checked" && outcome.stdout && (
          <pre className="rounded bg-black/30 p-2 font-mono text-xs text-neutral-400">{outcome.stdout}</pre>
        )}
      </div>
    </div>
  );
}
