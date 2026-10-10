import { useMemo } from "react";
import type { Frame, StageInfo, TableState } from "../frames";
import { Controls, usePlayback, usePlayerKeys } from "./Controls";
import { layoutAll } from "./layout";
import { Stage, StaticLayout } from "./Stage";
import { usePlayer, type PlayerStore } from "./store";

const NO_STAGES: StageInfo[] = [];

/** Stage strip: one pill per stage; click to jump. Highlights the playing stage. */
export function StageStrip({ store }: { store: PlayerStore }) {
  const stages = usePlayer((s) => s.trace?.stages ?? NO_STAGES, store);
  const stage = usePlayer((s) => s.layouts[s.index]?.frame.stage ?? 0, store);
  if (stages.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {stages.map((st, i) => (
        <button
          key={st.index}
          onClick={() => store.getState().seek(st.firstFrame)}
          className={`rounded-full border px-2.5 py-0.5 text-xs transition-colors ${
            stage === st.index
              ? "border-amber-400/60 bg-amber-400/15 text-amber-200"
              : stage > st.index
                ? "border-white/10 bg-white/5 text-neutral-300"
                : "border-white/10 text-neutral-500"
          }`}
          title={st.label}
        >
          <span className="mr-1 font-mono text-[10px] opacity-60">{i + 1}</span>
          {st.label}
        </button>
      ))}
    </div>
  );
}

export function VisualPlayer({
  store,
  keys = false,
  maxScale,
  empty,
}: {
  store: PlayerStore;
  keys?: boolean;
  maxScale?: number;
  empty?: React.ReactNode;
}) {
  usePlayback(store);
  usePlayerKeys(store, keys);
  const hasTrace = usePlayer((s) => s.layouts.length > 0, store);
  const note = usePlayer((s) => s.trace?.note, store);
  return (
    <div className="flex flex-col gap-3">
      <StageStrip store={store} />
      <div className="min-h-[120px] overflow-hidden rounded-lg border border-white/5 bg-black/20 p-3">
        {hasTrace ? <Stage store={store} maxScale={maxScale} /> : empty}
      </div>
      {note && <p className="text-xs text-amber-300/80">{note}</p>}
      <Controls store={store} />
    </div>
  );
}

/** One or more tables drawn statically with the stage's visual language. */
export function TableView({ tables, maxScale = 1, center = false }: { tables: TableState[]; maxScale?: number; center?: boolean }) {
  const layout = useMemo(() => {
    const frame: Frame = { index: 0, stage: 0, primitive: "show", label: "", tables, links: [], code: null, duration: 0 };
    return layoutAll([frame])[0];
  }, [tables]);
  return <StaticLayout layout={layout} maxScale={maxScale} center={center} />;
}
