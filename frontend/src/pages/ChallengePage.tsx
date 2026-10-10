import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useChallenge, useChallenges, useProgress } from "@/api/hooks";
import type { ChallengeDetail } from "@/api/types";
import { DescriptionTab } from "@/challenge/DescriptionTab";
import { HintsTab } from "@/challenge/HintsTab";
import { ResultPanel } from "@/challenge/ResultPanel";
import { SubmissionsTab } from "@/challenge/SubmissionsTab";
import { useChallengeSession, type ChallengeSession } from "@/challenge/useChallengeSession";
import { CodeEditor } from "@/components/CodeEditor";
import { EngineStatusPill } from "@/components/EngineStatus";
import { Split } from "@/components/Split";
import { Button, Tabs } from "@/components/ui";
import { currentFrame, usePlayer } from "@/engine/player/store";

function Arrow({ dir }: { dir: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2">
      <path d={dir === "left" ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6"} />
    </svg>
  );
}

function TopBar({ ch, session }: { ch: ChallengeDetail; session: ChallengeSession }) {
  const { data: path } = useChallenges();
  const { data: progress } = useProgress();
  const nav = useNavigate();
  const next = path?.find((c) => c.slug === ch.next_slug);
  const overall = progress?.overall;
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-white/5 bg-panel px-3">
      <Link to="/" className="flex items-center gap-2 rounded-md px-2 py-1 text-sm font-semibold text-neutral-200 hover:bg-white/5">
        <img src="/favicon.svg" alt="" className="h-5 w-5" /> Path
      </Link>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" disabled={!ch.prev_slug} onClick={() => ch.prev_slug && nav(`/c/${ch.prev_slug}`)} title="Previous challenge">
          <Arrow dir="left" />
        </Button>
        <span className="max-w-[40vw] truncate text-sm text-neutral-200">
          <span className="font-mono text-neutral-500">{ch.order}.</span> {ch.title}
        </span>
        <Button
          variant="ghost"
          size="sm"
          disabled={!ch.next_slug || next?.locked}
          onClick={() => ch.next_slug && nav(`/c/${ch.next_slug}`)}
          title={next?.locked ? "Solve this challenge to unlock the next one" : "Next challenge"}
        >
          <Arrow dir="right" />
        </Button>
      </div>
      <div className="flex flex-1 justify-center">
        <Button variant="success" onClick={() => void session.submit()} disabled={session.submitting} title="Run, animate and check (Ctrl+Enter)">
          {session.submitting ? "Running…" : "Submit"}
        </Button>
      </div>
      <EngineStatusPill />
      {overall && (
        <div className="flex items-center gap-2 text-xs text-neutral-400" title={`Total ${overall.total_score} pts`}>
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(overall.solved / Math.max(1, overall.total)) * 100}%` }} />
          </div>
          <span className="font-mono">
            {overall.solved}/{overall.total}
          </span>
        </div>
      )}
    </header>
  );
}

function Editor({ session }: { session: ChallengeSession }) {
  const frameCode = usePlayer((s) => currentFrame(s)?.code ?? null, session.player);
  const highlight = session.traceCode === session.code ? frameCode : null;
  const errorLine = session.outcome.kind === "error" ? session.outcome.error.line : null;
  return (
    <div className="flex h-full flex-col bg-[#1e1e1e]">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-white/5 bg-panel px-4 text-sm">
        <span className="font-medium text-neutral-200">Code</span>
        <span className="text-xs text-neutral-500">Python · pandas</span>
        <div className="flex-1" />
        <span className="text-xs text-neutral-500">
          worth <span className="font-mono text-amber-300">{session.potential}</span> pts
        </span>
      </div>
      <div className="min-h-0 flex-1">
        <CodeEditor value={session.code} onChange={session.setCode} highlight={highlight} errorLine={errorLine} onSubmit={() => void session.submit()} />
      </div>
    </div>
  );
}

type Tab = "description" | "hints" | "submissions";

function Screen({ ch }: { ch: ChallengeDetail }) {
  const session = useChallengeSession(ch);
  const [tab, setTab] = useState<Tab>("description");
  const helpCount = session.helpUsed.size;
  return (
    <div className="flex h-full flex-col">
      <TopBar ch={ch} session={session} />
      <div className="min-h-0 flex-1 p-2">
        <Split
          id="main"
          direction="row"
          initial={0.4}
          min={0.25}
          max={0.65}
          first={
            <div className="flex h-full flex-col overflow-hidden rounded-lg bg-panel">
              <Tabs
                tabs={[
                  { id: "description", label: "Description" },
                  { id: "hints", label: <>Hints{helpCount ? <span className="ml-1 text-xs text-amber-300">({helpCount})</span> : null}</> },
                  { id: "submissions", label: "Submissions" },
                ]}
                value={tab}
                onChange={setTab}
              />
              <div className="min-h-0 flex-1 overflow-y-auto">
                {tab === "description" && <DescriptionTab ch={ch} />}
                {tab === "hints" && <HintsTab ch={ch} session={session} />}
                {tab === "submissions" && <SubmissionsTab ch={ch} session={session} />}
              </div>
            </div>
          }
          second={
            <Split
              id="right"
              direction="column"
              initial={0.34}
              min={0.15}
              max={0.75}
              first={<div className="h-full overflow-hidden rounded-lg">{<Editor session={session} />}</div>}
              second={<div className="h-full overflow-hidden rounded-lg">{<ResultPanel ch={ch} session={session} />}</div>}
            />
          }
        />
      </div>
    </div>
  );
}

export default function ChallengePage() {
  const { slug = "" } = useParams();
  const { data: ch, isLoading, error } = useChallenge(slug);
  if (isLoading) return <div className="p-6 text-sm text-neutral-500">Loading challenge…</div>;
  if (error || !ch) {
    return (
      <div className="space-y-3 p-6 text-sm">
        <p className="text-red-300">{error?.message ?? "Challenge not found."}</p>
        <Link to="/" className="text-sky-300 hover:underline">
          ← Back to the path
        </Link>
      </div>
    );
  }
  if (ch.locked) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-neutral-400">
        <div className="text-3xl">🔒</div>
        <p>
          <span className="text-neutral-200">{ch.title}</span> unlocks when you solve the previous challenge.
        </p>
        <Link to={ch.prev_slug ? `/c/${ch.prev_slug}` : "/"} className="text-sky-300 hover:underline">
          Go to the previous challenge
        </Link>
      </div>
    );
  }
  return <Screen key={ch.slug} ch={ch} />;
}
