/**
 * Layout engine: turns frames into absolutely positioned elements.
 *
 * Geometry is computed, never measured from the DOM, so every frame's layout
 * is known up front. That makes stepping free, lets SVG links and
 * cell-moves know exact coordinates, and keeps all animation on
 * transform/opacity. Column widths are fixed per (table, column) across the
 * whole run, so nothing jitters when rows come and go.
 */
import type { CellText, Frame, Mark, Primitive, TableState } from "../frames";

export const ROW_H = 30;
export const HEAD_H = 40;
export const TITLE_H = 24;
export const GROUP_GAP = 12;
export const GAP_X = 64;
export const GAP_Y = 40;
export const PAD = 6;
const CHAR_W = 7.3;
const CELL_PAD = 26;
const COL_MIN = 54;
const COL_MAX = 220;
const BADGE_MIN = 40;
const CELL_INSET = 2;

export type ElKind = "cell" | "header" | "badge" | "ihdr" | "title" | "scalar" | "note";

export interface El {
  key: string;
  kind: ElKind;
  x: number;
  y: number;
  w: number;
  h: number;
  text: CellText;
  sub?: string;
  mark?: Mark;
  /** Palette index: row identity colour for badges, column colour for headers. */
  color?: number;
  group?: number;
  numeric?: boolean;
  scan?: number;
  /** Row position, used for staggering. */
  order: number;
  opacity: number;
  /** Enter from this position instead of fading in place. */
  from?: { x: number; y: number };
  ghost?: boolean;
  /** True when the element did not exist in the previous frame. */
  entering: boolean;
}

export interface LinkGeom {
  id: string;
  d: string;
  kind: "match" | "nomatch";
}

export interface Layout {
  frame: Frame;
  els: El[];
  byKey: Map<string, El>;
  links: LinkGeom[];
  width: number;
  height: number;
}

interface Sizing {
  col: Map<string, number>;
  badge: Map<string, number>;
  scalar: Map<string, number>;
}

const textW = (s: CellText | undefined) => (s ? s.length : 3) * CHAR_W;
const clampCol = (w: number) => Math.max(COL_MIN, Math.min(COL_MAX, Math.ceil(w)));
const NUMERIC = /^(u?int|float|Int|UInt|Float|complex)/;

function measure(frames: Frame[]): Sizing {
  const col = new Map<string, number>();
  const badge = new Map<string, number>();
  const scalar = new Map<string, number>();
  const bump = (m: Map<string, number>, k: string, w: number) => m.set(k, Math.max(m.get(k) ?? 0, w));
  for (const f of frames) {
    for (const t of f.tables) {
      if (t.kind === "scalar") {
        bump(scalar, t.id, Math.max(96, textW(t.scalar) * 1.45 + 40));
        continue;
      }
      bump(badge, t.id, Math.max(BADGE_MIN, textW(t.indexName ?? "") + 18));
      t.columns.forEach((c, j) => {
        let w = Math.max(textW(c.name) + 8, textW(c.dtype) * 0.85);
        for (const r of t.rows) w = Math.max(w, textW(r.cells[j]));
        bump(col, `${t.id}:${c.id}`, clampCol(w + CELL_PAD));
      });
      for (const r of t.rows) bump(badge, t.id, Math.max(BADGE_MIN, textW(r.label) + 22));
    }
  }
  return { col, badge, scalar };
}

function tableSize(t: TableState, s: Sizing): { w: number; h: number } {
  if (t.kind === "scalar") return { w: s.scalar.get(t.id) ?? 96, h: TITLE_H + 52 };
  const gaps = t.rows.filter((r) => r.gapBefore).length;
  const w = (s.badge.get(t.id) ?? BADGE_MIN) + t.columns.reduce((a, c) => a + (s.col.get(`${t.id}:${c.id}`) ?? COL_MIN), 0);
  const h = TITLE_H + HEAD_H + t.rows.length * ROW_H + gaps * GROUP_GAP + (t.note ? 22 : 0);
  return { w, h };
}

function placeTables(tables: TableState[], s: Sizing): Map<string, { x: number; y: number }> {
  const sizes = new Map(tables.map((t) => [t.id, tableSize(t, s)]));
  const slotRows = [...new Set(tables.map((t) => t.slot[1]))].sort((a, b) => a - b);
  const out = new Map<string, { x: number; y: number }>();
  let y = PAD;
  for (const sr of slotRows) {
    const inRow = tables.filter((t) => t.slot[1] === sr).sort((a, b) => a.slot[0] - b.slot[0]);
    let x = PAD;
    let rowH = 0;
    for (const t of inRow) {
      const sz = sizes.get(t.id)!;
      out.set(t.id, { x, y });
      x += sz.w + GAP_X;
      rowH = Math.max(rowH, sz.h);
    }
    y += rowH + GAP_Y;
  }
  return out;
}

function layoutTable(t: TableState, at: { x: number; y: number }, s: Sizing, push: (el: Omit<El, "entering" | "opacity"> & { opacity?: number }, origin?: string | null) => void) {
  const { x: tx, y: ty } = at;
  if (t.kind === "scalar") {
    const w = s.scalar.get(t.id) ?? 96;
    if (t.title) push({ key: `title:${t.id}`, kind: "title", x: tx, y: ty, w, h: TITLE_H, text: t.title, order: 0 });
    push({ key: `scalar:${t.id}`, kind: "scalar", x: tx, y: ty + TITLE_H, w, h: 48, text: t.scalar ?? null, mark: t.scalarMark, order: 0 });
    return;
  }
  const badgeW = s.badge.get(t.id) ?? BADGE_MIN;
  const colX: number[] = [];
  let cx = tx + badgeW;
  for (const c of t.columns) {
    colX.push(cx);
    cx += s.col.get(`${t.id}:${c.id}`) ?? COL_MIN;
  }
  const width = cx - tx;
  if (t.title) push({ key: `title:${t.id}`, kind: "title", x: tx, y: ty, w: width, h: TITLE_H, text: t.title, order: 0 });
  const hy = ty + TITLE_H;
  push({ key: `ihdr:${t.id}`, kind: "ihdr", x: tx, y: hy, w: badgeW - CELL_INSET, h: HEAD_H - CELL_INSET, text: t.indexName ?? "", order: 0 });
  t.columns.forEach((c, j) => {
    const w = (s.col.get(`${t.id}:${c.id}`) ?? COL_MIN) - CELL_INSET;
    push({
      key: `hdr:${t.id}:${c.id}`,
      kind: "header",
      x: colX[j],
      y: hy,
      w,
      h: HEAD_H - CELL_INSET,
      text: t.kind === "series" && !c.name ? "" : c.name,
      sub: c.dtype,
      color: c.color,
      mark: c.mark,
      numeric: NUMERIC.test(c.dtype),
      order: 0,
    });
  });
  let ry = hy + HEAD_H;
  t.rows.forEach((r, i) => {
    if (r.gapBefore) ry += GROUP_GAP;
    push(
      {
        key: r.badgeKey ?? `badge:${r.id}`,
        kind: "badge",
        x: tx,
        y: ry,
        w: badgeW - CELL_INSET,
        h: ROW_H - CELL_INSET,
        text: r.label ?? null,
        color: r.color,
        mark: r.badgeMark ?? (r.mark === "removed" || r.mark === "missing" || r.mark === "extra" ? r.mark : undefined),
        group: r.group,
        order: i,
      },
      r.badgeOrigin,
    );
    t.columns.forEach((c, j) => {
      const colMark = c.mark === "focus" ? "focus" : undefined;
      push(
        {
          key: r.cellKeys?.[j] ?? `${r.id}|${c.id}`,
          kind: "cell",
          x: colX[j],
          y: ry,
          w: (s.col.get(`${t.id}:${c.id}`) ?? COL_MIN) - CELL_INSET,
          h: ROW_H - CELL_INSET,
          text: r.cells[j],
          mark: r.cellMarks?.[j] ?? r.mark ?? colMark,
          group: r.group,
          numeric: NUMERIC.test(c.dtype),
          scan: r.scan?.[j] ?? undefined,
          order: i,
        },
        r.origins?.[j],
      );
    });
    ry += ROW_H;
  });
  if (t.note) push({ key: `note:${t.id}`, kind: "note", x: tx, y: ry + 4, w: width, h: 18, text: t.note, order: 0 });
}

function linkPath(a: El, b: El): string {
  let x1 = a.x + a.w;
  let x2 = b.x;
  if (b.x + b.w < a.x) {
    x1 = a.x;
    x2 = b.x + b.w;
  }
  const y1 = a.y + a.h / 2;
  const y2 = b.y + b.h / 2;
  const dx = Math.max(24, Math.abs(x2 - x1) * 0.45);
  const sgn = x2 >= x1 ? 1 : -1;
  return `M ${x1} ${y1} C ${x1 + dx * sgn} ${y1}, ${x2 - dx * sgn} ${y2}, ${x2} ${y2}`;
}

function layoutFrame(frame: Frame, s: Sizing, prev: Layout | null): Layout {
  const els: El[] = [];
  const byKey = new Map<string, El>();
  const origins: [El, string][] = [];
  const pos = placeTables(frame.tables, s);
  const push = (el: Omit<El, "entering" | "opacity"> & { opacity?: number }, origin?: string | null) => {
    let key = el.key;
    while (byKey.has(key)) key += "#dup";
    const full: El = { ...el, key, opacity: el.opacity ?? 1, entering: !prev?.byKey.has(key) };
    els.push(full);
    byKey.set(key, full);
    if (origin) origins.push([full, origin]);
  };
  for (const t of frame.tables) layoutTable(t, pos.get(t.id)!, s, push);

  for (const [el, origin] of origins) {
    if (!el.entering) continue;
    const src = prev?.byKey.get(origin) ?? byKey.get(origin);
    if (src) el.from = { x: src.x + (src.w - el.w) / 2, y: src.y + (src.h - el.h) / 2 };
  }
  // ghosts: elements of the previous frame folding into a target
  for (const t of frame.tables) {
    for (const g of t.ghosts ?? []) {
      const src = prev?.byKey.get(g.key);
      const target = byKey.get(g.target);
      if (!src || !target || byKey.has(g.key)) continue;
      const ghost: El = {
        ...src,
        x: target.x + (target.w - src.w) / 2,
        y: target.y + (target.h - src.h) / 2,
        opacity: 0,
        ghost: true,
        entering: false,
        from: undefined,
        scan: undefined,
      };
      els.push(ghost);
      byKey.set(g.key, ghost);
    }
  }
  const links: LinkGeom[] = [];
  for (const l of frame.links) {
    const a = byKey.get(l.from);
    const b = byKey.get(l.to);
    if (a && b) links.push({ id: l.id, d: linkPath(a, b), kind: l.kind });
  }
  let width = 0;
  let height = 0;
  for (const el of els) {
    if (el.ghost) continue;
    width = Math.max(width, el.x + el.w);
    height = Math.max(height, el.y + el.h);
  }
  return { frame, els, byKey, links, width: width + PAD, height: height + PAD };
}

/** Lay out every frame of a run once. */
export function layoutAll(frames: Frame[]): Layout[] {
  const s = measure(frames);
  const out: Layout[] = [];
  let prev: Layout | null = null;
  for (const f of frames) {
    prev = layoutFrame(f, s, prev);
    out.push(prev);
  }
  return out;
}

export function stageSize(layouts: Layout[]): { width: number; height: number } {
  let width = 0;
  let height = 0;
  for (const l of layouts) {
    width = Math.max(width, l.width);
    height = Math.max(height, l.height);
  }
  return { width, height };
}

export type { Primitive };
