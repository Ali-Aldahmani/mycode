/**
 * Player state. One store per player instance (the main stage, the example,
 * the reference solution and submission replays each get their own).
 * Components subscribe to slices, so a frame change re-renders only the stage
 * and the controls, never the page.
 */
import { createContext, useContext } from "react";
import { createStore, useStore, type StoreApi } from "zustand";
import type { Frame, Trace } from "../frames";
import { layoutAll, type Layout } from "./layout";
import { DEFAULT_SPEED_INDEX, SPEEDS } from "./primitives";

export interface PlayerState {
  trace: Trace | null;
  layouts: Layout[];
  index: number;
  playing: boolean;
  speedIdx: number;
  /** Bumped on every load, so the stage can tell a new run from a step. */
  runKey: number;
  load: (trace: Trace, opts?: { keepPosition?: boolean; autoplay?: boolean }) => void;
  clear: () => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  step: (delta: number) => void;
  seek: (index: number) => void;
  replay: () => void;
  setSpeedIdx: (i: number) => void;
}

export type PlayerStore = StoreApi<PlayerState>;

const SPEED_KEY = "pvt.speed";

function savedSpeed(): number {
  try {
    const v = Number(localStorage.getItem(SPEED_KEY));
    return Number.isInteger(v) && v >= 0 && v < SPEEDS.length && localStorage.getItem(SPEED_KEY) !== null
      ? v
      : DEFAULT_SPEED_INDEX;
  } catch {
    return DEFAULT_SPEED_INDEX;
  }
}

export function createPlayer(): PlayerStore {
  return createStore<PlayerState>()((set, get) => {
    const last = () => Math.max(0, get().layouts.length - 1);
    const instant = () => !Number.isFinite(SPEEDS[get().speedIdx]);
    return {
      trace: null,
      layouts: [],
      index: 0,
      playing: false,
      speedIdx: savedSpeed(),
      runKey: 0,
      load: (trace, opts = {}) => {
        const layouts = layoutAll(trace.frames);
        const lastIdx = Math.max(0, layouts.length - 1);
        let index = 0;
        if (opts.keepPosition) index = Math.min(get().index, lastIdx);
        const autoplay = opts.autoplay ?? true;
        if (autoplay && instant()) index = lastIdx;
        set({
          trace,
          layouts,
          index,
          playing: autoplay && !instant() && !opts.keepPosition && lastIdx > 0,
          runKey: get().runKey + 1,
        });
      },
      clear: () => set({ trace: null, layouts: [], index: 0, playing: false }),
      play: () => {
        if (instant()) return set({ index: last(), playing: false });
        set({ playing: true, index: get().index >= last() ? 0 : get().index });
      },
      pause: () => set({ playing: false }),
      toggle: () => (get().playing ? get().pause() : get().play()),
      step: (delta) => set({ playing: false, index: Math.max(0, Math.min(last(), get().index + delta)) }),
      seek: (index) => set({ playing: false, index: Math.max(0, Math.min(last(), index)) }),
      replay: () => {
        if (instant()) return set({ index: last(), playing: false });
        set({ index: 0, playing: true });
      },
      setSpeedIdx: (i) => {
        try {
          localStorage.setItem(SPEED_KEY, String(i));
        } catch {
          /* storage unavailable */
        }
        const speed = SPEEDS[i];
        if (!Number.isFinite(speed)) set({ speedIdx: i, playing: false, index: last() });
        else set({ speedIdx: i });
      },
    };
  });
}

export const PlayerContext = createContext<PlayerStore | null>(null);

export function usePlayer<T>(selector: (s: PlayerState) => T, store?: PlayerStore): T {
  const ctx = useContext(PlayerContext);
  const s = store ?? ctx;
  if (!s) throw new Error("usePlayer needs a PlayerContext or a store");
  return useStore(s, selector);
}

export function currentFrame(s: PlayerState): Frame | null {
  return s.layouts[s.index]?.frame ?? null;
}
