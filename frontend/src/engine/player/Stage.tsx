import { AnimatePresence, motion } from "framer-motion";
import { memo, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { El, Layout, LinkGeom } from "./layout";
import { stageSize } from "./layout";
import { colColor, groupColor, rowColor } from "./palette";
import { makeTiming, SPEEDS, type Timing } from "./primitives";
import { usePlayer, type PlayerStore } from "./store";

/** Scale-to-fit wrapper shared by the animated stage and static tables. */
function useFitScale(width: number, maxScale = 1) {
  const ref = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const ro = new ResizeObserver(([entry]) => setAvail(entry.contentRect.width));
    ro.observe(node);
    setAvail(node.clientWidth);
    return () => ro.disconnect();
  }, []);
  const scale = avail > 0 && width > 0 ? Math.min(maxScale, avail / width) : 1;
  return { ref, scale, avail };
}

const CellContent = memo(function CellContent({ text, delay, duration }: { text: El["text"]; delay: number; duration: number }) {
  const shown = text === null ? "NaN" : text;
  return (
    <AnimatePresence initial={false}>
      <motion.span
        key={shown}
        className="stage-text"
        initial={{ opacity: 0, y: -7 }}
        animate={{ opacity: 1, y: 0, transition: { delay, duration } }}
        exit={{ opacity: 0, y: 7, transition: { delay, duration: duration * 0.8 } }}
      >
        {shown}
      </motion.span>
    </AnimatePresence>
  );
});

const StageNode = memo(function StageNode({ el, timing }: { el: El; timing: Timing }) {
  const style: CSSProperties & Record<string, string | number> = { width: el.w, height: el.h };
  if (el.kind === "badge" && el.color != null) style["--row"] = rowColor(el.color);
  if (el.kind === "header" && el.color != null) style["--col"] = colColor(el.color);
  if (el.group != null) style["--tint"] = groupColor(el.group);
  style.zIndex = el.ghost ? 4 : el.from ? 3 : el.kind === "title" ? 0 : 1;

  const initial = el.from
    ? { x: el.from.x, y: el.from.y, opacity: 0.9, scale: 1 }
    : { x: el.x, y: el.y + (el.kind === "cell" || el.kind === "badge" ? 5 : 0), opacity: 0, scale: 0.9 };
  const scanDelay = el.scan != null && timing.primitive === "scan" ? el.scan * timing.scanStep : 0;
  const swapDuration = timing.instant ? 0 : Math.max(0.12, timing.base * 0.9);

  return (
    <motion.div
      className="stage-el"
      data-kind={el.kind}
      data-mark={el.mark}
      data-nan={el.text === null && (el.kind === "cell" || el.kind === "scalar") ? "" : undefined}
      data-num={el.numeric ? "" : undefined}
      data-group={el.group != null ? "" : undefined}
      style={style}
      initial={initial}
      animate={{ x: el.x, y: el.y, opacity: el.opacity, scale: 1 }}
      exit={{ opacity: 0, scale: 0.94, transition: timing.exit }}
      transition={timing.move(el)}
    >
      {el.kind === "header" ? (
        <>
          <span className="stage-head-name">{el.text}</span>
          <span className="stage-head-dtype">{el.sub}</span>
        </>
      ) : el.kind === "cell" || el.kind === "scalar" ? (
        <CellContent text={el.text} delay={scanDelay} duration={swapDuration} />
      ) : (
        <span className="stage-text">{el.text}</span>
      )}
      {el.scan != null && (timing.primitive === "scan" || timing.primitive === "collapse") && !timing.instant && (
        <motion.span
          key={`flash-${timing.frame}`}
          className="stage-flash"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.95, 0] }}
          transition={{ delay: scanDelay, duration: Math.max(0.2, timing.scanStep * 3.2), times: [0, 0.25, 1] }}
        />
      )}
    </motion.div>
  );
});

function Links({ links, timing, width, height }: { links: LinkGeom[]; timing: Timing; width: number; height: number }) {
  return (
    <svg className="pointer-events-none absolute left-0 top-0" width={width} height={height} style={{ zIndex: 2 }}>
      <AnimatePresence>
        {links.map((l) => (
          <motion.path
            key={l.id}
            d={l.d}
            className={l.kind === "match" ? "stage-link" : "stage-link stage-link-nomatch"}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            exit={{ opacity: 0, transition: timing.exit }}
            transition={timing.link}
          />
        ))}
      </AnimatePresence>
    </svg>
  );
}

function Canvas({ layout, timing, width, height, scale, offsetX }: { layout: Layout; timing: Timing; width: number; height: number; scale: number; offsetX: number }) {
  return (
    <div
      className="absolute left-0 top-0 origin-top-left"
      style={{ width, height, transform: `translate(${offsetX}px, 0) scale(${scale})` }}
    >
      <Links links={layout.links} timing={timing} width={width} height={height} />
      <AnimatePresence>
        {layout.els.map((el) => (
          <StageNode key={el.key} el={el} timing={timing} />
        ))}
      </AnimatePresence>
    </div>
  );
}

/** The animated stage. Subscribes only to what it draws. */
export function Stage({ store, maxScale = 1.15 }: { store?: PlayerStore; maxScale?: number }) {
  const layouts = usePlayer((s) => s.layouts, store);
  const index = usePlayer((s) => s.index, store);
  const speedIdx = usePlayer((s) => s.speedIdx, store);
  const size = useMemo(() => stageSize(layouts), [layouts]);
  const { ref, scale, avail } = useFitScale(size.width, maxScale);
  const layout = layouts[index];
  const timing = useMemo(
    () => makeTiming(layout?.frame.primitive ?? "show", index, SPEEDS[speedIdx]),
    [layout, index, speedIdx],
  );
  const offsetX = Math.max(0, (avail - size.width * scale) / 2);
  return (
    <div ref={ref} className="relative w-full" style={{ height: layout ? size.height * scale : 0 }}>
      {layout && (
        <Canvas layout={layout} timing={timing} width={size.width} height={size.height} scale={scale} offsetX={offsetX} />
      )}
    </div>
  );
}

/** A non-animated table (inputs, targets, diffs) drawn with the same visual language. */
export function StaticLayout({ layout, maxScale = 1, center = false }: { layout: Layout; maxScale?: number; center?: boolean }) {
  const { ref, scale, avail } = useFitScale(layout.width, maxScale);
  const timing = useMemo(() => makeTiming("show", 0, Infinity), []);
  const offsetX = center ? Math.max(0, (avail - layout.width * scale) / 2) : 0;
  return (
    <div ref={ref} className="relative w-full" style={{ height: layout.height * scale }}>
      <Canvas layout={layout} timing={timing} width={layout.width} height={layout.height} scale={scale} offsetX={offsetX} />
    </div>
  );
}
