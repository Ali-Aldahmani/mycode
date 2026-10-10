import { useCallback, useRef, useState, type ReactNode } from "react";

/** Two panes with a draggable divider. The ratio is remembered per `id`. */
export function Split({
  id,
  direction,
  initial,
  min = 0.2,
  max = 0.8,
  first,
  second,
}: {
  id: string;
  direction: "row" | "column";
  initial: number;
  min?: number;
  max?: number;
  first: ReactNode;
  second: ReactNode;
}) {
  const key = `pvt.split.${id}`;
  const [ratio, setRatio] = useState(() => {
    try {
      const v = Number(localStorage.getItem(key));
      return v > 0 && v < 1 ? v : initial;
    } catch {
      return initial;
    }
  });
  const box = useRef<HTMLDivElement>(null);
  const row = direction === "row";

  const onDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const el = box.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      let last = ratio;
      const move = (ev: PointerEvent) => {
        const r = row ? (ev.clientX - rect.left) / rect.width : (ev.clientY - rect.top) / rect.height;
        last = Math.min(max, Math.max(min, r));
        setRatio(last);
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        document.body.style.cursor = "";
        try {
          localStorage.setItem(key, String(last));
        } catch {
          /* storage unavailable */
        }
      };
      document.body.style.cursor = row ? "col-resize" : "row-resize";
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [ratio, row, min, max, key],
  );

  return (
    <div ref={box} className={`flex h-full w-full min-h-0 min-w-0 ${row ? "flex-row" : "flex-col"}`}>
      <div className="min-h-0 min-w-0 overflow-hidden" style={{ flexBasis: `${ratio * 100}%`, flexShrink: 0 }}>
        {first}
      </div>
      <div
        onPointerDown={onDown}
        className={`group relative z-10 shrink-0 ${row ? "w-2 cursor-col-resize" : "h-2 cursor-row-resize"}`}
      >
        <div
          className={`absolute rounded-full bg-white/5 transition-colors group-hover:bg-amber-400/50 ${
            row ? "inset-y-0 left-[3px] w-0.5" : "inset-x-0 top-[3px] h-0.5"
          }`}
        />
      </div>
      <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{second}</div>
    </div>
  );
}
