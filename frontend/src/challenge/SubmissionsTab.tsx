import { useSubmissions } from "@/api/hooks";
import type { ChallengeDetail } from "@/api/types";
import { Button, StatusPill, scoreColor, timeAgo } from "@/components/ui";
import type { ChallengeSession } from "./useChallengeSession";

const HELP_LABEL = { example: "example", hint_1: "hint 1", hint_2: "hint 2" } as const;

export function SubmissionsTab({ ch, session }: { ch: ChallengeDetail; session: ChallengeSession }) {
  const { data, isLoading, error } = useSubmissions(ch.slug);
  if (isLoading) return <div className="p-5 text-sm text-neutral-500">Loading…</div>;
  if (error) return <div className="p-5 text-sm text-red-300">{error.message}</div>;
  if (!data?.length) return <div className="p-5 text-sm text-neutral-500">No submissions yet. Press Submit to run and check your code.</div>;
  return (
    <ul className="divide-y divide-white/5">
      {data.map((s) => (
        <li key={s.id} className="group px-5 py-3 hover:bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <StatusPill status={s.status} />
            <span className={`font-mono text-sm ${scoreColor(s.score)}`}>{s.score != null ? `${s.score} pts` : ""}</span>
            <span className="text-xs text-neutral-500">
              {s.attempt_number != null ? `attempt ${s.attempt_number}` : "not counted"}
              {s.round > 1 ? ` · round ${s.round}` : ""}
            </span>
            <div className="flex-1" />
            <span className="text-xs text-neutral-500">{timeAgo(s.created_at)}</span>
          </div>
          {(s.hints_used.length > 0 || s.reason || s.error) && (
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
              {s.hints_used.map((h) => (
                <span key={h} className="rounded bg-amber-400/10 px-1.5 py-0.5 text-amber-200/80">
                  {HELP_LABEL[h]}
                </span>
              ))}
              {s.reason && <span className="text-neutral-400">{s.reason}</span>}
              {s.error && <span className="font-mono text-red-300/80">{s.error}</span>}
            </div>
          )}
          <pre className="mt-2 max-h-24 overflow-hidden rounded bg-black/30 px-3 py-2 font-mono text-xs text-neutral-300">{s.code}</pre>
          <div className="mt-2 flex gap-2 opacity-70 group-hover:opacity-100">
            <Button size="sm" variant="subtle" onClick={() => void session.replay(s.code, `Submission from ${timeAgo(s.created_at)}`)}>
              ▶ Replay animation
            </Button>
            <Button size="sm" variant="ghost" onClick={() => session.setCode(s.code)}>
              Load into editor
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
