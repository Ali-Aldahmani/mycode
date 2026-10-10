/**
 * Motion primitives: how each primitive moves elements in time.
 *
 * Every primitive is expressed as transitions on transform + opacity only
 * (GPU-composited). The layout decides *where* elements go; this file decides
 * *when* and *how fast*.
 *
 *   fade_out    marked elements exit; survivors close the gap afterwards
 *   slide       elements glide to their new position
 *   appear      new elements fade/scale in, lightly staggered by row
 *   scan        cells update one row after another (flash + value swap)
 *   cluster     rows glide into their group
 *   collapse    group members fold onto the summary row, which then appears
 *   connect     link lines draw, then result cells fly in from their sources
 *   move_cells  cells travel to new rows/columns, staggered by row
 */
import type { Transition } from "framer-motion";
import type { Primitive } from "../frames";
import type { El } from "./layout";

/** Seconds at 1x. */
const BASE: Record<Primitive, number> = {
  show: 0.4,
  fade_out: 0.42,
  slide: 0.62,
  appear: 0.42,
  scan: 0.3,
  cluster: 0.6,
  collapse: 0.62,
  connect: 0.55,
  move_cells: 0.72,
};

/** Seconds between two scan steps at 1x (matches SCAN_STEP in contract.py). */
export const SCAN_STEP = 0.14;

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export interface Timing {
  primitive: Primitive;
  frame: number;
  instant: boolean;
  speed: number;
  base: number;
  scanStep: number;
  move: (el: El) => Transition;
  exit: Transition;
  link: Transition;
}

export function makeTiming(primitive: Primitive, frame: number, speed: number): Timing {
  const instant = !Number.isFinite(speed);
  const k = instant ? 0 : 1 / speed;
  const base = BASE[primitive] * k;
  const scanStep = SCAN_STEP * k;
  const zero: Transition = { duration: 0 };

  const delayFor = (el: El): number => {
    if (instant) return 0;
    switch (primitive) {
      case "fade_out":
        return el.entering ? 0 : base * 0.7; // survivors move after the removed fade
      case "scan":
        return el.scan != null && el.entering ? el.scan * scanStep : 0;
      case "appear":
        return el.entering ? Math.min(el.order, 12) * 0.035 * k : 0;
      case "collapse":
        return el.entering ? base * 0.75 : 0;
      case "connect":
        return el.from ? base * 0.9 + Math.min(el.order, 12) * 0.07 * k : 0;
      case "move_cells":
        return Math.min(el.order, 16) * 0.045 * k;
      default:
        return 0;
    }
  };

  return {
    primitive,
    frame,
    instant,
    speed,
    base,
    scanStep,
    move: (el) =>
      instant
        ? zero
        : {
            x: { duration: base, ease: EASE, delay: delayFor(el) },
            y: { duration: base, ease: EASE, delay: delayFor(el) },
            scale: { duration: base * 0.8, ease: EASE, delay: delayFor(el) },
            opacity: {
              duration: el.ghost ? base * 1.1 : base * 0.8,
              ease: "easeOut",
              delay: el.ghost ? base * 0.25 : delayFor(el),
            },
          },
    exit: instant ? zero : { duration: Math.max(0.12, base * 0.7), ease: "easeOut" },
    link: instant ? zero : { duration: base * 1.2, ease: EASE },
  };
}

/** Speed steps for the slider; Infinity = instant (jump to the end state). */
export const SPEEDS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, Infinity] as const;
export const DEFAULT_SPEED_INDEX = 3;

export function speedLabel(speed: number): string {
  return Number.isFinite(speed) ? `${speed}x` : "instant";
}
