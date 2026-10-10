/**
 * Everything that happens on the challenge screen, in one place:
 *   submit  -> run in the browser -> animate immediately
 *           -> check against the target (in the worker)
 *           -> record on the backend in parallel (never blocks the visual)
 *   playground -> every edit re-runs (debounced) and keeps the frame position
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useOpenHelp, useSubmit } from "@/api/hooks";
import type { ChallengeDetail, HelpKind, SubmissionResult } from "@/api/types";
import { getChecker, getRunner } from "@/engine/engine";
import type { TableState } from "@/engine/frames";
import { createPlayer } from "@/engine/player/store";
import type { CheckResult, Inputs, RunError } from "@/engine/types";

export type Outcome =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "error"; error: RunError; stdout: string }
  | {
      kind: "checked";
      verdict: CheckResult;
      output: TableState;
      stdout: string;
      submission: SubmissionResult | null;
      saveError: string | null;
    }
  | { kind: "replay"; output: TableState; label: string }
  | { kind: "playground"; output: TableState | null; error: RunError | null };

const draftKey = (slug: string) => `pvt.draft.${slug}`;

function loadDraft(slug: string, fallback: string): string {
  try {
    return localStorage.getItem(draftKey(slug)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function useChallengeSession(ch: ChallengeDetail) {
  const player = useMemo(() => createPlayer(), []);
  const [code, setCodeState] = useState(() => loadDraft(ch.slug, ch.starter_code));
  // the latest code, readable before React re-renders (Ctrl+Enter right after typing)
  const codeRef = useRef(code);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  /** The code that produced the trace on the stage (for editor highlighting). */
  const [traceCode, setTraceCode] = useState<string | null>(null);
  const [helpUsed, setHelpUsed] = useState<Set<HelpKind>>(() => new Set(ch.help_used));
  const [playground, setPlaygroundState] = useState(false);
  const [playInputs, setPlayInputs] = useState<Inputs>(ch.inputs);
  const [submittedOnce, setSubmittedOnce] = useState(ch.submitted);
  const submit = useSubmit(ch.slug);
  const help = useOpenHelp(ch.slug);
  const busy = useRef(false);

  useEffect(() => setHelpUsed(new Set(ch.help_used)), [ch.help_used]);

  const setCode = useCallback(
    (v: string) => {
      codeRef.current = v;
      setCodeState(v);
      try {
        localStorage.setItem(draftKey(ch.slug), v);
      } catch {
        /* storage unavailable */
      }
    },
    [ch.slug],
  );

  const flags = useCallback(
    () => ({
      used_example: helpUsed.has("example"),
      used_hint_1: helpUsed.has("hint_1"),
      used_hint_2: helpUsed.has("hint_2"),
    }),
    [helpUsed],
  );

  const doSubmit = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setPlaygroundState(false);
    setOutcome({ kind: "running" });
    try {
      const src = codeRef.current;
      const res = await getRunner(ch.language).run(src, ch.inputs, { library: ch.library, visualType: ch.visual_type });
      if (!res.ok) {
        if ("stale" in res) return;
        // errors are shown but never count as an attempt
        setOutcome({ kind: "error", error: res.error, stdout: res.stdout });
        submit.mutate({
          challenge_slug: ch.slug,
          code: src,
          status: "error",
          ...flags(),
          error: `${res.error.type}: ${res.error.message}`.slice(0, 2000),
        });
        return;
      }
      setTraceCode(src);
      player.getState().load(res.trace, { autoplay: true });
      const verdict = await getChecker(ch.checker_type).check(res.runId, ch.target, ch.checker_options);
      setOutcome({ kind: "checked", verdict, output: res.output, stdout: res.stdout, submission: null, saveError: null });
      setSubmittedOnce(true);
      submit.mutate(
        {
          challenge_slug: ch.slug,
          code: src,
          status: verdict.passed ? "correct" : "wrong",
          ...flags(),
          reason: verdict.reason || null,
          runtime_ms: res.ms,
        },
        {
          onSuccess: (saved) => {
            setOutcome((o) => (o.kind === "checked" ? { ...o, submission: saved } : o));
            if (saved.submission.status === "correct") setHelpUsed(new Set());
          },
          onError: (e) => setOutcome((o) => (o.kind === "checked" ? { ...o, saveError: e.message } : o)),
        },
      );
    } finally {
      busy.current = false;
    }
  }, [ch, flags, player, submit]);

  /** Play any code on the challenge inputs (submission replay, reference solution). */
  const replay = useCallback(
    async (src: string, label: string) => {
      setPlaygroundState(false);
      const res = await getRunner(ch.language).run(src, ch.inputs, { library: ch.library, visualType: ch.visual_type });
      if (!res.ok) {
        if (!("stale" in res)) setOutcome({ kind: "error", error: res.error, stdout: res.stdout });
        return;
      }
      setTraceCode(src);
      player.getState().load(res.trace, { autoplay: true });
      setOutcome({ kind: "replay", output: res.output, label });
    },
    [ch, player],
  );

  // ---------------------------------------------------------------- playground
  const runPlayground = useCallback(
    async (src: string, inputs: Inputs) => {
      const res = await getRunner(ch.language).run(src, inputs, { library: ch.library, visualType: ch.visual_type, latestOnly: true });
      if (!res.ok) {
        if ("stale" in res) return;
        setOutcome({ kind: "playground", output: null, error: res.error });
        return;
      }
      setTraceCode(src);
      player.getState().load(res.trace, { keepPosition: true, autoplay: false });
      setOutcome({ kind: "playground", output: res.output, error: null });
    },
    [ch, player],
  );

  const debounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    if (!playground) return;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => void runPlayground(code, playInputs), 100);
    return () => clearTimeout(debounce.current);
  }, [playground, code, playInputs, runPlayground]);

  const setPlayground = useCallback(
    (on: boolean) => {
      setPlaygroundState(on);
      if (on) setOutcome({ kind: "playground", output: null, error: null });
    },
    [],
  );

  const resetInputs = useCallback(() => setPlayInputs(ch.inputs), [ch.inputs]);

  // ---------------------------------------------------------------- help
  const openHelp = useCallback(
    (kind: HelpKind) => {
      setHelpUsed((s) => new Set(s).add(kind));
      help.mutate(kind);
    },
    [help],
  );

  const potential = useMemo(() => {
    let p = 100;
    for (const k of helpUsed) p -= ch.costs[k];
    // wrong-attempt penalty is owned by the backend; ch.potential already includes it
    const backendHelp = ch.help_used.reduce((a, k) => a + ch.costs[k], 0);
    const wrongPenalty = 100 - backendHelp - ch.potential;
    return Math.max(0, p - Math.max(0, wrongPenalty));
  }, [helpUsed, ch]);

  return {
    player,
    code,
    setCode,
    outcome,
    traceCode,
    submit: doSubmit,
    submitting: outcome.kind === "running",
    replay,
    playground,
    setPlayground,
    canPlayground: submittedOnce,
    playInputs,
    setPlayInputs,
    resetInputs,
    helpUsed,
    openHelp,
    potential,
  };
}

export type ChallengeSession = ReturnType<typeof useChallengeSession>;
