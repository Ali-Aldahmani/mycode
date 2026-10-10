/**
 * Frame contract, TypeScript side.
 *
 * Everything visual is a list of frames. Python frame generators (see
 * /pyengine/contract.py, which mirrors this file) produce them; the generic
 * player plays them. Every frame is a complete snapshot, so stepping in any
 * direction costs nothing.
 *
 * Element keys (shared convention with Python):
 *   cell    "<rowId>|<colId>"
 *   badge   "badge:<rowId>"
 *   header  "hdr:<tableId>:<colId>"
 *   scalar  "scalar:<tableId>"
 * Same key in two consecutive frames = the element moves. New key = appears.
 * Missing key = fades out.
 */

export type Primitive =
  | "show"
  | "fade_out" // rows/columns/cells removed
  | "slide" // rows change position
  | "appear" // new rows/columns/values
  | "scan" // cell-by-cell sweep
  | "cluster" // rows group by colour
  | "collapse" // groups fold into one row
  | "connect" // lines between matching keys
  | "move_cells"; // cells travel between rows and columns

export type Mark =
  | "kept"
  | "removed"
  | "changed"
  | "new"
  | "focus"
  | "source"
  | "nomatch"
  | "wrong"
  | "missing"
  | "extra";

/** Display text of a cell. `null` = missing value (NaN/None/NaT), drawn gray. */
export type CellText = string | null;

export interface ColumnState {
  id: string;
  name: string;
  dtype: string;
  /** Index into the column palette. */
  color: number;
  mark?: Mark;
}

export interface RowState {
  /** Stable row identity, e.g. "df:3". Drives the identity colour and animation. */
  id: string;
  /** Index label as displayed. */
  label?: CellText;
  /** Index into the row palette. */
  color: number;
  /** One entry per column, aligned with TableState.columns. */
  cells: CellText[];
  mark?: Mark;
  badgeMark?: Mark;
  /** Group number while clustering (tints the row). */
  group?: number;
  /** Extra space above this row (separates clusters). */
  gapBefore?: boolean;
  cellMarks?: (Mark | null)[];
  /** Override the element key of a cell (the cell *is* an element from an earlier frame). */
  cellKeys?: (string | null)[];
  /** The cell enters from the position of this element key. */
  origins?: (string | null)[];
  /** Scan order: the cell flashes / updates at step N of the sweep. */
  scan?: (number | null)[];
  badgeKey?: string;
  badgeOrigin?: string;
}

export interface Ghost {
  /** Element (from the previous frame) that folds into `target` and fades out. */
  key: string;
  target: string;
}

export interface TableState {
  id: string;
  title: string;
  kind: "dataframe" | "series" | "scalar";
  /** Grid slot [column, row] on the stage. */
  slot: [number, number];
  indexName?: string;
  showIndex?: boolean;
  columns: ColumnState[];
  rows: RowState[];
  scalar?: string;
  scalarMark?: Mark;
  ghosts?: Ghost[];
  note?: string;
}

export interface Link {
  id: string;
  from: string;
  to: string;
  kind: "match" | "nomatch";
}

/** 1-based lines/columns, end exclusive (Monaco convention). */
export interface CodeRange {
  startLine: number;
  startCol: number;
  endLine: number;
  endCol: number;
}

export interface Frame {
  index: number;
  /** Stage number (0 = the input before any code runs). */
  stage: number;
  primitive: Primitive;
  label: string;
  tables: TableState[];
  links: Link[];
  code: CodeRange | null;
  /** How long the frame is held at 1x speed, in ms. */
  duration: number;
}

export interface StageInfo {
  index: number;
  label: string;
  op: string;
  code: CodeRange | null;
  firstFrame: number;
  lastFrame: number;
}

export interface Trace {
  frames: Frame[];
  stages: StageInfo[];
  /** False when visual mode is off (tables over 20 rows). */
  visual: boolean;
  note?: string | null;
}
