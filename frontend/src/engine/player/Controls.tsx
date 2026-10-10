import { useEffect } from "react";
import { SPEEDS, speedLabel } from "./primitives";
import { currentFrame, usePlayer, type PlayerStore } from "./store";

/** Advances frames while playing. Mount once per player. */
export function usePlayback(store: PlayerStore) {
  const playing = usePlayer((s) => s.playing, store);
  const index = usePlayer((s) => s.index, store);
  const speedIdx = usePlayer((s) => s.speedIdx, store);
  const runKey = usePlayer((s) => s.runKey, store);
  useEffect(() => {
    if (!playing) return;
    const s = store.getState();
    const last = s.layouts.length - 1;
    if (index >= last) {
      store.setState({ playing: false });
      return;
    }
    const frame = s.layouts[index].frame;
    const speed = SPEEDS[speedIdx];
    const wait = Number.isFinite(speed) ? frame.duration / speed : 0;
    const t = setTimeout(() => store.setState({ index: index + 1 }), wait);
    return () => clearTimeout(t);
  }, [playing, index, speedIdx, runKey, store]);
}

const btn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md text-neutral-300 hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent";

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  play: "M8 5.5v13a1 1 0 0 0 1.5.86l10.2-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z",
  pause: "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z",
  back: "M17 6v12l-8.5-6L17 6ZM6 6h2v12H6z",
  fwd: "M7 6v12l8.5-6L7 6Zm9 0h2v12h-2z",
  replay: "M12 5V2L7 6.5 12 11V8a5 5 0 1 1-5 5H5a7 7 0 1 0 7-8Z",
};

export function Controls({ store }: { store: PlayerStore }) {
  const index = usePlayer((s) => s.index, store);
  const total = usePlayer((s) => s.layouts.length, store);
  const playing = usePlayer((s) => s.playing, store);
  const speedIdx = usePlayer((s) => s.speedIdx, store);
  const label = usePlayer((s) => currentFrame(s)?.label ?? "", store);
  const a = store.getState();
  const disabled = total === 0;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <div className="flex items-center gap-0.5">
        <button className={btn} title="Step back (←)" disabled={disabled || index === 0} onClick={() => a.step(-1)}>
          <Icon d={ICONS.back} />
        </button>
        <button
          className={`${btn} h-9 w-9 bg-white/5`}
          title={playing ? "Pause (space)" : "Play (space)"}
          disabled={disabled}
          onClick={() => a.toggle()}
        >
          <Icon d={playing ? ICONS.pause : ICONS.play} />
        </button>
        <button className={btn} title="Step forward (→)" disabled={disabled || index >= total - 1} onClick={() => a.step(1)}>
          <Icon d={ICONS.fwd} />
        </button>
        <button className={btn} title="Replay (r)" disabled={disabled} onClick={() => a.replay()}>
          <Icon d={ICONS.replay} />
        </button>
      </div>
      <span className="w-14 font-mono text-xs tabular-nums text-neutral-500">
        {total ? `${index + 1}/${total}` : "–"}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm text-neutral-300" title={label}>
        {label}
      </span>
      <label className="flex items-center gap-2 text-xs text-neutral-500">
        <span className="hidden sm:inline">slow</span>
        <input
          type="range"
          min={0}
          max={SPEEDS.length - 1}
          step={1}
          value={speedIdx}
          onChange={(e) => a.setSpeedIdx(Number(e.target.value))}
          className="speed-slider w-28"
          aria-label="Animation speed"
        />
        <span className="w-14 font-mono text-neutral-300">{speedLabel(SPEEDS[speedIdx])}</span>
      </label>
    </div>
  );
}

/** Keyboard shortcuts for a player: space, arrows, r. Ignored while typing. */
export function usePlayerKeys(store: PlayerStore, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.closest(".monaco-editor") || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable)) return;
      const s = store.getState();
      if (e.key === " ") {
        e.preventDefault();
        s.toggle();
      } else if (e.key === "ArrowRight") s.step(1);
      else if (e.key === "ArrowLeft") s.step(-1);
      else if (e.key === "r" && !e.ctrlKey && !e.metaKey) s.replay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [store, enabled]);
}
