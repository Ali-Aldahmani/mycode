import { useMemo, useState } from "react";
import type { ChallengeDetail, HelpKind } from "@/api/types";
import { CodeEditor } from "@/components/CodeEditor";
import { Button, RichText } from "@/components/ui";
import { getRunner } from "@/engine/engine";
import { createPlayer, currentFrame, usePlayer } from "@/engine/player/store";
import { TableView, VisualPlayer } from "@/engine/player/VisualPlayer";
import type { ChallengeSession } from "./useChallengeSession";

function Locked({ kind, cost, onOpen, label, description }: { kind: HelpKind; cost: number; onOpen: (k: HelpKind) => void; label: string; description: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3">
      <div>
        <div className="text-sm font-medium text-neutral-200">{label}</div>
        <div className="text-xs text-neutral-500">{description}</div>
      </div>
      <Button variant="subtle" onClick={() => onOpen(kind)}>
        Open <span className="font-mono text-amber-300">−{cost}</span>
      </Button>
    </div>
  );
}

function Example({ ch }: { ch: ChallengeDetail }) {
  const store = useMemo(() => createPlayer(), []);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const highlight = usePlayer((s) => currentFrame(s)?.code ?? null, store);
  const play = async () => {
    const res = await getRunner(ch.language).run(ch.example.code, ch.example.inputs, { visualType: ch.visual_type });
    if (!res.ok) {
      if (!("stale" in res)) setError(`${res.error.type}: ${res.error.message}`);
      return;
    }
    setLoaded(true);
    store.getState().load(res.trace, { autoplay: true });
  };
  const lines = ch.example.code.split("\n").length;
  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-400">The same method on different data.</p>
      <div className="rounded-lg bg-black/20 p-3">
        <TableView tables={ch.display.example_inputs} />
      </div>
      <div className="overflow-hidden rounded-lg border border-white/5" style={{ height: lines * 22 + 28 }}>
        <CodeEditor value={ch.example.code} readOnly highlight={loaded ? highlight : null} />
      </div>
      {ch.example.note && <p className="text-sm text-neutral-400">{ch.example.note}</p>}
      {!loaded ? (
        <Button variant="success" onClick={() => void play()}>
          ▶ Play the example
        </Button>
      ) : (
        <VisualPlayer store={store} />
      )}
      {error && <p className="font-mono text-xs text-red-300">{error}</p>}
    </div>
  );
}

export function HintsTab({ ch, session }: { ch: ChallengeDetail; session: ChallengeSession }) {
  const { helpUsed, openHelp } = session;
  return (
    <div className="space-y-5 p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-white">Help</h2>
        <span className="text-xs text-neutral-500">
          A correct answer is worth <span className="font-mono text-amber-300">{session.potential}</span> points now
        </span>
      </div>
      <p className="text-xs leading-relaxed text-neutral-500">
        Each kind of help is charged once. The docs link on the Description tab is always free.
      </p>

      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Example</h3>
        {helpUsed.has("example") ? (
          <Example ch={ch} />
        ) : (
          <Locked kind="example" cost={ch.costs.example} onOpen={openHelp} label="See an example" description="The same method used on different data, animated." />
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Hint 1</h3>
        {helpUsed.has("hint_1") ? (
          <p className="rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3 text-sm leading-relaxed text-neutral-200">
            <RichText text={ch.hint_1} />
          </p>
        ) : (
          <Locked kind="hint_1" cost={ch.costs.hint_1} onOpen={openHelp} label="Direction" description="Which way to go, without the syntax." />
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Hint 2</h3>
        {helpUsed.has("hint_2") ? (
          <pre className="overflow-x-auto rounded-lg border border-white/5 bg-black/30 px-4 py-3 font-mono text-sm text-amber-200">
            {ch.hint_2}
          </pre>
        ) : (
          <Locked kind="hint_2" cost={ch.costs.hint_2} onOpen={openHelp} label="Syntax pattern" description="The shape of the code, with blanks to fill." />
        )}
      </section>
    </div>
  );
}
