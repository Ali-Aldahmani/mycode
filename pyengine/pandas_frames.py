"""Frame generator for pandas table transforms (visual_type family "pandas").

Input: the stages recorded by the tracer. Output: a flat list of frames in the
contract format (see contract.py), plus per-stage info for the stage strip.

How a stage is turned into frames
---------------------------------
1. Row identity. Every input row gets a stable id (`df:3`). If a stage keeps
   the index labels (filter, sort, new column, fillna...), rows keep their ids
   ("tracked") and a generic diff produces fade_out / slide / appear / scan
   frames.
2. When identity cannot be tracked (groupby aggregation, merge, melt, pivot,
   reductions...), an operation-specific generator uses *provenance*: it
   re-runs the operation with hidden position columns to learn which input
   cells produced which output cells, then animates with cluster/collapse,
   connect or move_cells.
3. If nothing else applies, the stage cross-fades to the new value, tagged
   with the challenge's declared `visual_type` primitive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import contract as C
from .tracer import Stage, Step, is_table
from .valuespec import col_name, fmt, fmt_label

MAX_ROWS = 20
MAX_COLS = 12
STATIC_ROWS = 60  # rows rendered when visual mode is off

AGG_METHODS = {
    "sum", "mean", "median", "min", "max", "count", "size", "std", "var", "prod",
    "first", "last", "nunique", "agg", "aggregate", "describe", "sem",
}
BREAKING = {
    "merge", "join", "concat", "melt", "pivot", "pivot_table", "stack", "unstack",
    "explode", "value_counts", "describe", "crosstab", "T", "transpose", "corr", "cov",
}
POSITIONAL = {"reset_index", "set_index", "set_axis", "setattr_index"}
RENAMING = {"rename", "set_axis", "setattr_columns", "add_prefix", "add_suffix"}
SCAN_OPS = {
    "apply", "map", "applymap", "transform", "astype", "replace", "round", "abs", "clip",
    "upper", "lower", "title", "strip", "len", "contains", "startswith", "endswith", "split",
    "slice", "year", "month", "day", "dayofweek", "day_name", "month_name", "where", "mask",
    "isna", "isnull", "notna", "notnull", "duplicated", "cumsum", "cumprod", "cummax", "cummin",
    "shift", "diff", "pct_change", "rolling", "expanding", "rank", "between", "isin",
}


# --------------------------------------------------------------------------- views

@dataclass
class View:
    """A displayable value flattened to text cells."""
    kind: str  # dataframe | series | scalar
    names: list[str]
    dtypes: list[str]
    labels: list[Any]
    cells: list[list[str | None]]
    index_name: str | None
    scalar: str | None = None
    raw: Any = None

    @property
    def nrows(self) -> int:
        return len(self.labels)


def _index_name(idx: pd.Index) -> str | None:
    if isinstance(idx, pd.MultiIndex):
        names = [str(n) for n in idx.names if n is not None]
        return ", ".join(names) if names else None
    return None if idx.name is None else str(idx.name)


def as_table(v: Any) -> Any:
    if isinstance(v, pd.Index):
        return pd.Series(v, name=v.name)
    if isinstance(v, np.ndarray):
        return pd.Series(v) if v.ndim == 1 else pd.DataFrame(v)
    if isinstance(v, list):
        return pd.Series(v)
    return v


def view_of(value: Any) -> View:
    v = as_table(value)
    if isinstance(v, pd.DataFrame):
        data = v.astype(object).to_numpy() if len(v.columns) else np.empty((len(v), 0), dtype=object)
        return View(
            kind="dataframe",
            names=[col_name(c) for c in v.columns],
            dtypes=[str(t) for t in v.dtypes],
            labels=list(v.index),
            cells=[[fmt(x) for x in row] for row in data],
            index_name=_index_name(v.index),
            raw=v,
        )
    if isinstance(v, pd.Series):
        return View(
            kind="series",
            names=["" if v.name is None else col_name(v.name)],
            dtypes=[str(v.dtype)],
            labels=list(v.index),
            cells=[[fmt(x)] for x in v.astype(object)],
            index_name=_index_name(v.index),
            raw=v,
        )
    text = fmt(v)
    return View("scalar", [], [], [], [], None, scalar="NaN" if text is None else text, raw=v)


def _unique(labels: list[Any]) -> bool:
    try:
        return len(set(labels)) == len(labels)
    except TypeError:
        return False


# --------------------------------------------------------------------------- ids

@dataclass
class Ident:
    rows: list[str]
    cols: list[str]


@dataclass
class TData:
    """A view with ids attached: what a table looks like at one moment."""
    kind: str
    index_name: str | None
    rows: list[str]
    labels: dict[str, str | None]
    cols: list[str]
    names: dict[str, str]
    dtypes: dict[str, str]
    cells: dict[tuple[str, str], str | None]
    scalar: str | None = None

    def copy(self) -> "TData":
        return TData(
            self.kind, self.index_name, list(self.rows), dict(self.labels), list(self.cols),
            dict(self.names), dict(self.dtypes), dict(self.cells), self.scalar,
        )


def tdata(view: View, ident: Ident) -> TData:
    cells: dict[tuple[str, str], str | None] = {}
    for r, rid in enumerate(ident.rows):
        for c, cid in enumerate(ident.cols):
            cells[(rid, cid)] = view.cells[r][c]
    return TData(
        kind=view.kind,
        index_name=view.index_name,
        rows=list(ident.rows),
        labels={rid: fmt_label(view.labels[i]) for i, rid in enumerate(ident.rows)},
        cols=list(ident.cols),
        names={cid: view.names[i] for i, cid in enumerate(ident.cols)},
        dtypes={cid: view.dtypes[i] for i, cid in enumerate(ident.cols)},
        cells=cells,
        scalar=view.scalar,
    )


# --------------------------------------------------------------------------- generator

@dataclass
class Marks:
    rows: dict[str, str] = field(default_factory=dict)
    cols: dict[str, str] = field(default_factory=dict)
    cells: dict[tuple[str, str], str] = field(default_factory=dict)
    badges: dict[str, str] = field(default_factory=dict)
    groups: dict[str, int] = field(default_factory=dict)
    gaps: set[str] = field(default_factory=set)
    scan: dict[tuple[str, str], int] = field(default_factory=dict)
    cell_keys: dict[tuple[str, str], str] = field(default_factory=dict)
    origins: dict[tuple[str, str], str] = field(default_factory=dict)
    badge_keys: dict[str, str] = field(default_factory=dict)
    badge_origins: dict[str, str] = field(default_factory=dict)


class PandasFrameGenerator:
    """Turns traced stages into frames. One instance per run."""

    def __init__(self, stages: list[Stage], inputs: dict[str, Any], visual_type: str | None = None):
        self.stages = stages
        self.inputs = inputs
        self.visual_type = visual_type
        self.frames: list[dict] = []
        self.infos: list[dict] = []
        self.idents: dict[tuple, Ident] = {}
        self._row_color: dict[str, int] = {}
        self._col_color: dict[str, int] = {}
        self._next_row_color = 0
        self._next_col_color = 0
        self.stage_no = 0
        self.code: dict | None = None
        self.main_title = ""
        for name, value in inputs.items():
            self.idents[("input", name)] = self.fresh(view_of(value), name)

    # -- colours
    def row_color(self, rid: str) -> int:
        if rid not in self._row_color:
            self._row_color[rid] = self._next_row_color
            self._next_row_color += 1
        return self._row_color[rid]

    def col_color(self, cid: str) -> int:
        if cid not in self._col_color:
            self._col_color[cid] = self._next_col_color
            self._next_col_color += 1
        return self._col_color[cid]

    # -- identities
    def fresh(self, view: View, prefix: str) -> Ident:
        rows = [f"{prefix}:{i}" for i in range(view.nrows)]
        return Ident(rows, self._col_ids(view.names, prefix, {}))

    @staticmethod
    def _col_ids(names: list[str], prefix: str, reuse: dict[str, str]) -> list[str]:
        out: list[str] = []
        used: set[str] = set()
        for name in names:
            cid = reuse.get(name)
            if cid is None or cid in used:
                cid = f"{prefix}.{name}"
                k = 2
                while cid in used:
                    cid = f"{prefix}.{name}#{k}"
                    k += 1
            used.add(cid)
            out.append(cid)
        return out

    def ident_for(self, token: tuple | None, view: View, fallback_prefix: str) -> Ident:
        if token is not None and token in self.idents:
            ident = self.idents[token]
            if len(ident.rows) == view.nrows and len(ident.cols) == len(view.names):
                return ident
        return self.fresh(view, fallback_prefix)

    # -- rendering
    def render(
        self,
        td: TData,
        *,
        table_id: str = "main",
        title: str = "",
        slot: tuple[int, int] = (0, 0),
        rows: list[str] | None = None,
        cols: list[str] | None = None,
        marks: Marks | None = None,
        ghosts: list[dict] | None = None,
        scalar_mark: str | None = None,
        note: str | None = None,
        colors: dict[str, int] | None = None,
    ) -> dict:
        m = marks or Marks()
        rows = td.rows if rows is None else rows
        cols = td.cols if cols is None else cols
        if td.kind == "scalar":
            return C.table(table_id, title, "scalar", [], [], slot=slot, scalar=td.scalar,
                           scalar_mark=scalar_mark, ghosts=ghosts, note=note)
        columns = [
            C.column(cid, td.names.get(cid, ""), td.dtypes.get(cid, ""), self.col_color(cid), m.cols.get(cid))
            for cid in cols
        ]
        def cell_mark(rid: str, cid: str) -> str | None:
            own = m.cells.get((rid, cid))
            if own:
                return own
            col_mark = m.cols.get(cid)
            return col_mark if col_mark in ("removed", "new", "kept", "missing", "extra") else None

        out_rows = []
        for rid in rows:
            cell_marks = [cell_mark(rid, cid) for cid in cols]
            out_rows.append(
                C.row(
                    rid,
                    td.labels.get(rid),
                    (colors or {}).get(rid, self.row_color(rid)),
                    [td.cells.get((rid, cid)) for cid in cols],
                    mark=m.rows.get(rid),
                    badge_mark=m.badges.get(rid),
                    group=m.groups.get(rid),
                    gap_before=rid in m.gaps,
                    cell_marks=cell_marks,
                    cell_keys=[m.cell_keys.get((rid, cid)) for cid in cols],
                    origins=[m.origins.get((rid, cid)) for cid in cols],
                    scan=[m.scan.get((rid, cid)) for cid in cols],
                    badge_key_override=m.badge_keys.get(rid),
                    badge_origin=m.badge_origins.get(rid),
                )
            )
        return C.table(
            table_id, title, td.kind, columns, out_rows, slot=slot, index_name=td.index_name,
            ghosts=ghosts, note=note,
        )

    def emit(self, primitive: str, label: str, tables: list[dict], *, links=None, scan_rows: int = 0) -> None:
        for t in tables:
            if t["id"] == "main" and not t.get("title") and self.main_title:
                t["title"] = self.main_title
        self.frames.append(
            C.frame(primitive, label, tables, links=links, code=self.code, stage=self.stage_no, scan_rows=scan_rows)
        )

    # -- entry point
    def generate(self, result: Any, result_token: tuple | None) -> tuple[list[dict], list[dict]]:
        if self.stages:
            self.intro(self.stages[0])
        else:
            view = view_of(result)
            td = tdata(view, self.ident_for(result_token, view, "result"))
            self.code = None
            self.emit("show", "Result", [self.render(td, title="result")])
        for st in self.stages:
            self.stage_no = st.index
            self.code = st.code
            first = len(self.frames)
            label = describe(st)
            self.main_title = st.before_name or st.var or ""
            try:
                ident = self.stage(st, label)
            except Exception:  # noqa: BLE001 - a visual bug must never break a run
                del self.frames[first:]
                ident = self.crossfade(st, label)
            self.idents[("stage", st.index)] = ident
            if len(self.frames) == first:
                self.emit("show", label, [self.render(tdata(view_of(st.after), ident))])
            # the stage ends on the variable it assigns
            end = self.frames[-1]
            for t in end["tables"]:
                if t["id"] == "main" and st.var:
                    t["title"] = st.var
            self.infos.append(C.stage_info(st.index, label, main_op(st), st.code, first, len(self.frames) - 1))
        if self.stages and result_token != ("stage", self.stages[-1].index):
            self.stage_no = len(self.stages) + 1
            self.code = None
            view = view_of(result)
            td = tdata(view, self.ident_for(result_token, view, "result"))
            self.emit("show", "result", [self.render(td, title="result")])
        return C.finalize(self.frames), self.infos

    def intro(self, st: Stage) -> None:
        self.stage_no = 0
        self.code = None
        self.main_title = st.before_name or ""
        tables = []
        if st.inputs:
            # multi-table operation: every table gets slot i and id "in<i>"
            sources = ([(st.before, st.before_token, st.before_name or "")] if st.before is not None else []) + st.inputs
            for i, (value, token, name) in enumerate(sources):
                v = view_of(value)
                tables.append(self.render(tdata(v, self.ident_for(token, v, name or f"t{i}")),
                                          table_id=f"in{i}", title=name, slot=(i, 0)))
        elif st.before is not None:
            view = view_of(st.before)
            td = tdata(view, self.ident_for(st.before_token, view, st.before_name or f"s{st.index}in"))
            tables.append(self.render(td, title=st.before_name or ""))
        if tables:
            self.emit("show", "Input", tables)

    # -- dispatch
    def stage(self, st: Stage, label: str) -> Ident:
        ops = set(st.ops)
        after_view = view_of(st.after)
        if st.before is None and not st.inputs:
            return self.crossfade(st, label)
        name = main_op(st)
        special: dict[str, Callable[[Stage, str], Ident | None]] = {
            "merge": self.merge,
            "join": self.merge,
            "concat": self.concat,
            "melt": self.melt,
            "pivot": self.pivot,
            "pivot_table": self.pivot,
            "stack": self.stack,
            "unstack": self.unstack,
            "value_counts": self.value_counts,
        }
        if name in special:
            ident = special[name](st, label)
            if ident is not None:
                return ident
            return self.crossfade(st, label)
        if st.before is None:
            return self.crossfade(st, label)
        if "groupby" in ops:
            ident = self.groupby(st, label)
            if ident is not None:
                return ident
        before_view = view_of(st.before)
        if after_view.kind == "scalar" and before_view.kind != "scalar":
            return self.reduce(st, label)
        pi = self.ident_for(st.before_token, before_view, f"s{st.index}in")
        ni = self.derive(st, before_view, pi, after_view)
        if ni is not None:
            return self.diff(st, label, before_view, pi, after_view, ni)
        return self.crossfade(st, label)

    def derive(self, st: Stage, pv: View, pi: Ident, nv: View) -> Ident | None:
        if pv.kind == "scalar" or nv.kind == "scalar":
            return None
        ops = set(st.ops)
        if ops & BREAKING:
            return None
        if "groupby" in ops and ops & AGG_METHODS:
            return None
        positional = bool(ops & POSITIONAL)
        if positional:
            if nv.nrows != pv.nrows:
                return None
            rows = list(pi.rows)
        else:
            if not (_unique(pv.labels) and _unique(nv.labels)):
                return None
            if nv.index_name != pv.index_name and pv.index_name is not None:
                return None
            pos = {label: i for i, label in enumerate(pv.labels)}
            try:
                if not all(label in pos for label in nv.labels):
                    return None
            except TypeError:
                return None
            if pd.api.types.is_bool_dtype(pd.Index(nv.labels)) and not pd.api.types.is_bool_dtype(pd.Index(pv.labels)):
                return None
            rows = [pi.rows[pos[label]] for label in nv.labels]
        # columns
        if len(nv.names) == 1 and len(pv.names) == 1 and nv.kind == "series" and pv.kind == "series":
            cols = list(pi.cols)
        elif ops & RENAMING and len(nv.names) == len(pv.names):
            cols = list(pi.cols)
        else:
            reuse = {name: pi.cols[i] for i, name in enumerate(pv.names)}
            cols = self._col_ids(nv.names, f"s{st.index}", reuse)
        return Ident(rows, cols)

    # -- focus helpers
    @staticmethod
    def focus_cols(st: Stage, td: TData) -> list[str]:
        return [cid for cid in td.cols if td.names.get(cid) in st.refs]

    # ------------------------------------------------------------------ tracked diff
    def diff(self, st: Stage, label: str, pv: View, pi: Ident, nv: View, ni: Ident) -> Ident:
        P = tdata(pv, pi)
        N = tdata(nv, ni)
        focus = self.focus_cols(st, P)
        work = P.copy()
        cur_rows = list(P.rows)
        cur_cols = list(P.cols)
        op = main_op(st)

        def focus_marks() -> dict[str, str]:
            return {cid: "focus" for cid in focus if cid in cur_cols}

        # 1. rows removed
        removed = [r for r in P.rows if r not in set(N.rows)]
        if removed:
            kept = [r for r in cur_rows if r not in removed]
            m = Marks(rows={**{r: "removed" for r in removed}, **{r: "kept" for r in kept}}, cols=focus_marks())
            self.emit("fade_out", f"{label}: {len(removed)} row{'s' if len(removed) != 1 else ''} out",
                      [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)])
            cur_rows = kept
            self.emit("fade_out", f"{label}: {len(kept)} row{'s' if len(kept) != 1 else ''} kept",
                      [self.render(work, rows=cur_rows, cols=cur_cols,
                                   marks=Marks(rows={r: "kept" for r in kept}, cols=focus_marks()))])

        # 2. columns dropped
        dropped = [c for c in cur_cols if c not in set(N.cols)]
        if dropped and N.cols:
            m = Marks(cols={c: "removed" for c in dropped})
            for c in cur_cols:
                if c not in dropped:
                    m.cols[c] = "kept"
            self.emit("fade_out", f"{label}: drop {len(dropped)} column{'s' if len(dropped) != 1 else ''}",
                      [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)])
            cur_cols = [c for c in cur_cols if c not in dropped]
            if cur_cols:
                if N.kind == "series" and len(cur_cols) == 1:
                    work.kind = "series"
                self.emit("fade_out", f"{label}: columns kept",
                          [self.render(work, rows=cur_rows, cols=cur_cols, marks=Marks(cols={c: "kept" for c in cur_cols}))])

        # 3. rows reordered
        if [r for r in N.rows if r in cur_rows] != cur_rows or (set(N.rows) - set(cur_rows)):
            cur_rows = [r for r in N.rows if r in set(P.rows)]
            self.emit("slide", f"{label}: rows move into order",
                      [self.render(work, rows=cur_rows, cols=cur_cols, marks=Marks(cols=focus_marks()))])

        # 4. columns reordered
        common = [c for c in N.cols if c in cur_cols]
        if common != cur_cols and len(common) == len(cur_cols):
            cur_cols = common
            self.emit("slide", f"{label}: columns move into order",
                      [self.render(work, rows=cur_rows, cols=cur_cols)])

        # 5. index labels change (reset_index / set_index)
        relabel = [r for r in cur_rows if P.labels.get(r) != N.labels.get(r)]
        added = [c for c in N.cols if c not in set(P.cols)]
        if relabel or N.index_name != P.index_name:
            moved_from_index = op in ("reset_index",) and added
            for r in cur_rows:
                work.labels[r] = N.labels.get(r)
            work.index_name = N.index_name
            m = Marks(badges={r: "changed" for r in relabel})
            if moved_from_index:
                # the old index labels slide out of the badge into the new column(s)
                for c in added:
                    work.names[c] = N.names[c]
                    work.dtypes[c] = N.dtypes[c]
                    for r in cur_rows:
                        work.cells[(r, c)] = N.cells.get((r, c))
                        m.origins[(r, c)] = C.badge_key(r)
                        m.cells[(r, c)] = "new"
                cur_cols = [c for c in N.cols if c in set(cur_cols) | set(added)]
                added = []
            if op == "set_index":
                for c in dropped:
                    for r in cur_rows:
                        m.badge_origins[r] = C.cell_key(r, c)
            self.emit("move_cells" if moved_from_index else "appear", f"{label}: new index",
                      [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)])

        # 6. columns added
        if added:
            sources = [c for c in focus if c in cur_cols]
            for c in added:
                work.names[c] = N.names[c]
                work.dtypes[c] = N.dtypes[c]
                for r in cur_rows:
                    work.cells[(r, c)] = N.cells.get((r, c))
            if N.kind == "series" and not cur_cols:
                work.kind = "series"
            cur_cols = [c for c in N.cols if c in set(cur_cols) | set(added)]
            m = Marks()
            constant = all(len({N.cells.get((r, c)) for r in cur_rows}) <= 1 for c in added)
            use_scan = bool(sources) or (bool(set(st.ops) & SCAN_OPS) and not constant)
            if use_scan:
                for i, r in enumerate(cur_rows):
                    for c in added:
                        m.cells[(r, c)] = "new"
                        m.scan[(r, c)] = i
                    for s in sources:
                        m.cells[(r, s)] = "source"
                        m.scan[(r, s)] = i
                self.emit("scan", f"{label}: compute {', '.join(repr(N.names[c]) for c in added)} row by row",
                          [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)], scan_rows=len(cur_rows))
            else:
                for r in cur_rows:
                    for c in added:
                        m.cells[(r, c)] = "new"
                for c in added:
                    m.cols[c] = "new"
                self.emit("appear", f"{label}: new column{'s' if len(added) != 1 else ''} "
                          f"{', '.join(repr(N.names[c]) for c in added)}",
                          [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)])

        # 7. values / names / dtypes changed
        changed = [(r, c) for r in cur_rows for c in cur_cols
                   if c in set(P.cols) and work.cells.get((r, c)) != N.cells.get((r, c))]
        renamed = [c for c in cur_cols if c in set(P.cols) and P.names[c] != N.names.get(c)]
        retyped = [c for c in cur_cols if c in set(P.cols) and P.dtypes[c] != N.dtypes.get(c)]
        if changed or renamed or retyped:
            m = Marks()
            for c in renamed + retyped:
                m.cols[c] = "changed"
                work.names[c] = N.names[c]
                work.dtypes[c] = N.dtypes[c]
            fill = bool(changed) and all(work.cells.get(rc) is None for rc in changed)
            row_order = {r: i for i, r in enumerate(cur_rows)}
            col_order = {c: i for i, c in enumerate(cur_cols)}
            changed.sort(key=lambda rc: (row_order[rc[0]], col_order[rc[1]]))
            scanned_rows: dict[str, int] = {}
            for r, c in changed:
                work.cells[(r, c)] = N.cells.get((r, c))
                m.cells[(r, c)] = "changed"
                if not fill:
                    m.scan[(r, c)] = scanned_rows.setdefault(r, len(scanned_rows))
            if fill:
                prim, text = "appear", f"{label}: {len(changed)} value{'s' if len(changed) != 1 else ''} filled"
            elif changed:
                prim, text = "scan", f"{label}: {len(changed)} value{'s' if len(changed) != 1 else ''} changed"
            else:
                prim, text = "appear", f"{label}: header updated"
            if N.kind == "series" and len(cur_cols) == 1:
                work.kind = "series"
            self.emit(prim, text, [self.render(work, rows=cur_rows, cols=cur_cols, marks=m)],
                      scan_rows=len(scanned_rows) if prim == "scan" else 0)

        # 8. settle on the exact result
        self.emit("show", label, [self.render(N)])
        return ni

    # ------------------------------------------------------------------ fallback
    def crossfade(self, st: Stage, label: str) -> Ident:
        nv = view_of(st.after)
        ni = self.fresh(nv, f"s{st.index}")
        N = tdata(nv, ni)
        primitive = self.visual_type if self.visual_type in C.PRIMITIVES else "appear"
        if primitive in ("connect", "cluster", "collapse", "move_cells", "scan", "slide", "fade_out"):
            primitive = "appear"
        if st.before is not None and view_of(st.before).kind != "scalar":
            pv = view_of(st.before)
            P = tdata(pv, self.ident_for(st.before_token, pv, f"s{st.index}in"))
            focus = self.focus_cols(st, P)
            if focus:
                self.emit("show", f"{label}: uses {', '.join(repr(P.names[c]) for c in focus)}",
                          [self.render(P, marks=Marks(cols={c: "focus" for c in focus}))])
        m = Marks(rows={r: "new" for r in N.rows})
        self.emit(primitive, label, [self.render(N, marks=m, scalar_mark="new")])
        self.emit("show", label, [self.render(N)])
        return ni

    # ------------------------------------------------------------------ reductions
    def reduce(self, st: Stage, label: str) -> Ident:
        pv = view_of(st.before)
        P = tdata(pv, self.ident_for(st.before_token, pv, f"s{st.index}in"))
        nv = view_of(st.after)
        ni = Ident([], [])
        N = tdata(nv, ni)
        op = main_op(st)
        structural = op in ("shape", "size", "ndim", "len", "columns", "index", "dtypes", "empty")
        sources = self.focus_cols(st, P) or P.cols
        if not structural and P.rows:
            m = Marks()
            for i, r in enumerate(P.rows):
                for c in sources:
                    m.cells[(r, c)] = "source"
                    m.scan[(r, c)] = i
            self.emit("scan", f"{label}: read every value", [self.render(P, marks=m)], scan_rows=len(P.rows))
            target = C.scalar_key("main")
            ghosts = [C.ghost(C.cell_key(r, c), target) for r in P.rows for c in sources]
            self.emit("collapse", f"{label}: combine into one value",
                      [self.render(N, ghosts=ghosts, scalar_mark="new")])
        else:
            self.emit("appear", label, [self.render(N, scalar_mark="new")])
        self.emit("show", label, [self.render(N)])
        return ni

    # ------------------------------------------------------------------ groupby
    def groupby(self, st: Stage, label: str) -> Ident | None:
        gb_step = next((s for s in st.steps if s.name == "groupby"), None)
        if gb_step is None or not hasattr(gb_step.value, "indices"):
            return None
        pv = view_of(st.before)
        nv = view_of(st.after)
        if nv.kind == "scalar":
            return None
        indices = {k: list(v) for k, v in gb_step.value.indices.items()}
        by = gb_step.args[0] if gb_step.args else gb_step.kwargs.get("by")
        keys = [by] if isinstance(by, str) else list(by) if isinstance(by, (list, tuple)) else []
        as_index = gb_step.kwargs.get("as_index", True)
        return self.cluster_collapse(st, label, pv, nv, indices, keys, as_index)

    def value_counts(self, st: Stage, label: str) -> Ident | None:
        if st.before is None:
            return None
        pv = view_of(st.before)
        nv = view_of(st.after)
        raw = st.before
        if isinstance(raw, pd.Series):
            indices = {k: list(v) for k, v in raw.groupby(raw, sort=False).indices.items()}
            keys = [pv.names[0]]
        elif isinstance(raw, pd.DataFrame):
            subset = st.main.args[0] if st.main.args else st.main.kwargs.get("subset")
            cols = list(raw.columns) if subset is None else ([subset] if isinstance(subset, str) else list(subset))
            indices = {k: list(v) for k, v in raw.groupby(cols, sort=False).indices.items()}
            keys = [str(c) for c in cols]
        else:
            return None
        return self.cluster_collapse(st, label, pv, nv, indices, keys, True)

    def cluster_collapse(self, st: Stage, label: str, pv: View, nv: View, indices: dict, keys: list,
                         as_index: bool) -> Ident | None:
        P = tdata(pv, self.ident_for(st.before_token, pv, f"s{st.index}in"))
        # map every output row to its group key
        norm = {}
        for k, v in indices.items():
            norm[k] = v
            if isinstance(k, tuple) and len(k) == 1:
                norm[k[0]] = v
        out_keys: list[Any] = []
        if as_index:
            for label_value in nv.labels:
                if label_value not in norm:
                    return None
                out_keys.append(label_value)
        else:
            raw = nv.raw
            if not isinstance(raw, pd.DataFrame) or not all(k in raw.columns for k in keys):
                return None
            for _, row in raw[keys].iterrows():
                k = tuple(row) if len(keys) > 1 else row.iloc[0]
                if k not in norm:
                    return None
                out_keys.append(k)
        groups = {r_i: g for g, k in enumerate(out_keys) for r_i in norm[k]}
        key_cols = [cid for cid in P.cols if P.names[cid] in {str(k) for k in keys}]
        rid_group = {P.rows[i]: g for i, g in groups.items()}
        member_rows = [P.rows[i] for i in sorted(groups)]

        # 1. colour rows by group
        m = Marks(groups=rid_group, cols={c: "focus" for c in key_cols})
        self.emit("cluster", f"{label}: rows get their group colour", [self.render(P, marks=m)])
        # 2. gather groups
        ordered: list[str] = []
        gaps: set[str] = set()
        for g in range(len(out_keys)):
            members = [r for r in P.rows if rid_group.get(r) == g]
            if members and ordered:
                gaps.add(members[0])
            ordered.extend(members)
        dropped_rows = [r for r in P.rows if r not in rid_group]
        if dropped_rows:
            self.emit("fade_out", f"{label}: rows without a group key drop out",
                      [self.render(P, marks=Marks(groups=rid_group, rows={r: "removed" for r in dropped_rows}))])
        self.emit("cluster", f"{label}: rows gather into groups",
                  [self.render(P, rows=ordered, marks=Marks(groups=rid_group, gaps=gaps,
                                                             cols={c: "focus" for c in key_cols}))])
        # 3. drop columns the aggregation does not use
        out_first_level = set()
        raw = nv.raw
        if isinstance(raw, pd.DataFrame):
            for c in raw.columns:
                out_first_level.add(str(c[0]) if isinstance(c, tuple) else str(c))
        elif isinstance(raw, pd.Series) and raw.name is not None:
            out_first_level.add(str(raw.name[0]) if isinstance(raw.name, tuple) else str(raw.name))
        value_cols = [cid for cid in P.cols if P.names[cid] in out_first_level and cid not in key_cols]
        keep_cols = [cid for cid in P.cols if cid in key_cols or cid in value_cols]
        if keep_cols != P.cols:
            gone = [c for c in P.cols if c not in keep_cols]
            m = Marks(groups=rid_group, gaps=gaps, cols={c: "removed" for c in gone})
            self.emit("fade_out", f"{label}: keep only the columns used",
                      [self.render(P, rows=ordered, marks=m)])
            self.emit("fade_out", f"{label}: keep only the columns used",
                      [self.render(P, rows=ordered, cols=keep_cols, marks=Marks(groups=rid_group, gaps=gaps))])

        # 4. collapse into one row per group
        prefix = f"g{st.index}"
        nrows = [f"{prefix}:{i}" for i in range(nv.nrows)]
        reuse: dict[str, str] = {}
        for cid in value_cols:
            reuse.setdefault(P.names[cid], cid)
        ncols: list[str] = []
        used: set[str] = set()
        for name in nv.names:
            base = name.split(" ")[0] if name not in reuse else name
            cid = reuse.get(name) or reuse.get(base)
            if cid is None or cid in used:
                cid = f"{prefix}.{name}"
            used.add(cid)
            ncols.append(cid)
        ni = Ident(nrows, ncols)
        N = tdata(nv, ni)
        colors = {rid: self._group_color(g) for g, rid in enumerate(nrows)}
        ghosts: list[dict] = []
        name_to_ncol: dict[str, str] = {}
        for cid in ncols:
            nm = N.names[cid]
            name_to_ncol.setdefault(nm, cid)
            name_to_ncol.setdefault(nm.split(" ")[0], cid)
        for r in ordered:
            g = rid_group[r]
            target_row = nrows[g]
            ghosts.append(C.ghost(C.badge_key(r), C.badge_key(target_row)))
            for c in keep_cols:
                ncol = name_to_ncol.get(P.names[c])
                target = C.cell_key(target_row, ncol) if ncol and ncol in ncols else C.badge_key(target_row)
                ghosts.append(C.ghost(C.cell_key(r, c), target))
        m = Marks(rows={r: "new" for r in nrows}, groups={r: g for g, r in enumerate(nrows)})
        agg = main_op(st)
        self.emit("collapse", f"{label}: each group folds into one row ({agg})",
                  [self.render(N, marks=m, ghosts=ghosts, colors=colors)])
        self.emit("show", label, [self.render(N, colors=colors)])
        for rid, color in colors.items():
            self._row_color[rid] = color
        return ni

    @staticmethod
    def _group_color(g: int) -> int:
        return g * 3 + 1

    # ------------------------------------------------------------------ merge / join
    def merge(self, st: Stage, label: str) -> Ident | None:
        step = st.main
        is_join = step.name == "join"
        if step.kind == "func":
            if len(step.args) < 2 or not (is_table(step.args[0]) and is_table(step.args[1])):
                return None
            left, right, rest = step.args[0], step.args[1], list(step.args[2:])
            lname, rname = (st.inputs[0][2], st.inputs[1][2]) if len(st.inputs) >= 2 else ("left", "right")
            ltoken = st.inputs[0][1] if st.inputs else None
            rtoken = st.inputs[1][1] if len(st.inputs) > 1 else None
        else:
            left = st.before
            if left is None or not step.args and "right" not in step.kwargs and "other" not in step.kwargs:
                return None
            right = step.args[0] if step.args else step.kwargs.get("right", step.kwargs.get("other"))
            rest = list(step.args[1:])
            lname = st.before_name or "left"
            rname = st.inputs[0][2] if st.inputs else "right"
            ltoken = st.before_token
            rtoken = st.inputs[0][1] if st.inputs else None
        if not isinstance(left, pd.DataFrame) or not is_table(right):
            return None
        right_df = right.to_frame() if isinstance(right, pd.Series) else right
        kwargs = {k: v for k, v in step.kwargs.items() if k not in ("right", "other")}
        L = left.copy()
        R = right_df.copy()
        L["__lpos"] = np.arange(len(L))
        R["__rpos"] = np.arange(len(R))
        if is_join:
            aug = L.join(R, *rest, **kwargs)
        else:
            aug = pd.merge(L, R, *rest, **kwargs)
        after = st.after
        check = aug.drop(columns=["__lpos", "__rpos"])
        if not (isinstance(after, pd.DataFrame) and check.shape == after.shape and list(check.columns) == list(after.columns)):
            return None
        lpos = [None if pd.isna(x) else int(x) for x in aug["__lpos"]]
        rpos = [None if pd.isna(x) else int(x) for x in aug["__rpos"]]

        lv, rv, nv = view_of(left), view_of(right_df), view_of(after)
        Li = self.ident_for(ltoken, lv, lname)
        Ri = self.ident_for(rtoken, rv, rname)
        Ld, Rd = tdata(lv, Li), tdata(rv, Ri)

        on = kwargs.get("on")
        lkeys = kwargs.get("left_on", on)
        rkeys = kwargs.get("right_on", on)
        if is_join:
            lkeys, rkeys = on, None
        elif lkeys is None and not kwargs.get("left_index") and not kwargs.get("right_index"):
            common = [c for c in left.columns if c in right_df.columns]
            lkeys = rkeys = common
        as_list = lambda k: [] if k is None else ([k] if not isinstance(k, (list, tuple)) else list(k))  # noqa: E731
        lkeys, rkeys = as_list(lkeys), as_list(rkeys)
        lkey_cids = [Li.cols[list(left.columns).index(k)] for k in lkeys if k in left.columns]
        rkey_cids = [Ri.cols[list(right_df.columns).index(k)] for k in rkeys if k in right_df.columns]

        def lkey_el(i: int) -> str:
            rid = Li.rows[i]
            return C.cell_key(rid, lkey_cids[0]) if lkey_cids else C.badge_key(rid)

        def rkey_el(j: int) -> str:
            rid = Ri.rows[j]
            return C.cell_key(rid, rkey_cids[0]) if rkey_cids else C.badge_key(rid)

        pairs = sorted({(a, b) for a, b in zip(lpos, rpos) if a is not None and b is not None})
        links = [C.link(f"l{a}-{b}", lkey_el(a), rkey_el(b), "match") for a, b in pairs]
        lseen = {a for a in lpos if a is not None}
        rseen = {b for b in rpos if b is not None}
        lmatched = {a for a, _ in pairs}
        rmatched = {b for _, b in pairs}

        def side_marks(rows: list[str], seen: set[int], matched: set[int]) -> dict[str, str]:
            out = {}
            for i, rid in enumerate(rows):
                out[rid] = "kept" if i in matched else ("nomatch" if i in seen else "removed")
            return out

        lmarks = Marks(rows=side_marks(Li.rows, lseen, lmatched), cols={c: "focus" for c in lkey_cids})
        rmarks = Marks(rows=side_marks(Ri.rows, rseen, rmatched), cols={c: "focus" for c in rkey_cids})
        how = kwargs.get("how", "left" if is_join else "inner")
        ltable = lambda m: self.render(Ld, table_id="in0", title=lname, slot=(0, 0), marks=m)  # noqa: E731
        rtable = lambda m: self.render(Rd, table_id="in1", title=rname, slot=(1, 0), marks=m)  # noqa: E731
        self.emit("connect", f"{label}: match keys ({how})", [ltable(lmarks), rtable(rmarks)], links=links)

        # result rows come from the matched cells
        prefix = f"m{st.index}"
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], self._col_ids(nv.names, prefix, {}))
        N = tdata(nv, ni)
        suffixes = kwargs.get("suffixes", ("_x", "_y"))
        lsuf, rsuf = (kwargs.get("lsuffix", ""), kwargs.get("rsuffix", "")) if is_join else suffixes
        lcols = {str(c): Li.cols[i] for i, c in enumerate(left.columns)}
        rcols = {str(c): Ri.cols[i] for i, c in enumerate(right_df.columns)}

        def source(name: str) -> list[tuple[str, str]]:
            out = []
            if lsuf and name.endswith(str(lsuf)) and name[: -len(str(lsuf))] in lcols:
                out.append(("L", lcols[name[: -len(str(lsuf))]]))
            elif rsuf and name.endswith(str(rsuf)) and name[: -len(str(rsuf))] in rcols:
                out.append(("R", rcols[name[: -len(str(rsuf))]]))
            else:
                if name in lcols:
                    out.append(("L", lcols[name]))
                if name in rcols:
                    out.append(("R", rcols[name]))
            return out

        m = Marks(rows={r: "new" for r in N.rows})
        for i, rid in enumerate(N.rows):
            for cid in N.cols:
                for side, scid in source(N.names[cid]):
                    pos = lpos[i] if side == "L" else rpos[i]
                    if pos is not None:
                        m.origins[(rid, cid)] = C.cell_key((Li if side == "L" else Ri).rows[pos], scid)
                        break
                else:
                    if N.cells.get((rid, cid)) is None:
                        m.cells[(rid, cid)] = "nomatch"
            if lpos[i] is not None:
                m.badge_origins[rid] = C.badge_key(Li.rows[lpos[i]])
            elif rpos[i] is not None:
                m.badge_origins[rid] = C.badge_key(Ri.rows[rpos[i]])
        for i, rid in enumerate(N.rows):
            if lpos[i] is not None:
                self._row_color[rid] = self.row_color(Li.rows[lpos[i]])
            elif rpos[i] is not None:
                self._row_color[rid] = self.row_color(Ri.rows[rpos[i]])
        self.emit("connect", f"{label}: build one row per match",
                  [ltable(lmarks), rtable(rmarks), self.render(N, title="result", slot=(0, 1), marks=m)],
                  links=links)
        self.emit("show", label, [self.render(N, title="result")])
        return ni

    # ------------------------------------------------------------------ concat
    def concat(self, st: Stage, label: str) -> Ident | None:
        step = st.main
        objs = step.args[0] if step.args else step.kwargs.get("objs")
        if not isinstance(objs, (list, tuple)) or not all(is_table(o) for o in objs):
            return None
        kwargs = {k: v for k, v in step.kwargs.items() if k != "objs"}
        if kwargs.get("axis", 0) not in (0, "index"):
            return None
        frames = [o.to_frame() if isinstance(o, pd.Series) else o for o in objs]
        aug = pd.concat([f.assign(__src=i, __pos=np.arange(len(f))) for i, f in enumerate(frames)], **kwargs)
        after = st.after
        if not isinstance(after, pd.DataFrame) or len(aug) != len(after):
            return None
        src = [int(x) for x in aug["__src"]]
        pos = [int(x) for x in aug["__pos"]]
        names = [n for _, _, n in st.inputs] or [f"df{i}" for i in range(len(frames))]
        tokens = [t for _, t, _ in st.inputs] or [None] * len(frames)
        idents, datas, tables = [], [], []
        for i, f in enumerate(frames):
            v = view_of(f)
            ident = self.ident_for(tokens[i] if i < len(tokens) else None, v, names[i] if i < len(names) else f"df{i}")
            idents.append(ident)
            datas.append(tdata(v, ident))
            tables.append(self.render(datas[-1], table_id=f"in{i}", title=names[i] if i < len(names) else "",
                                      slot=(i, 0), marks=Marks(rows={r: "kept" for r in ident.rows})))
        self.emit("show", f"{label}: tables to stack", tables)
        nv = view_of(after)
        prefix = f"c{st.index}"
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], self._col_ids(nv.names, prefix, {}))
        N = tdata(nv, ni)
        m = Marks()
        used: set[str] = set()
        for i, rid in enumerate(N.rows):
            sd, ident, f = datas[src[i]], idents[src[i]], frames[src[i]]
            srid = ident.rows[pos[i]]
            names_to_cid = {sd.names[c]: c for c in sd.cols}
            for cid in N.cols:
                scid = names_to_cid.get(N.names[cid])
                if scid is None:
                    m.cells[(rid, cid)] = "nomatch"
                    continue
                key = C.cell_key(srid, scid)
                if key in used:
                    m.origins[(rid, cid)] = key
                else:
                    m.cell_keys[(rid, cid)] = key
                    used.add(key)
            bkey = C.badge_key(srid)
            if bkey in used:
                m.badge_origins[rid] = bkey
            else:
                m.badge_keys[rid] = bkey
                used.add(bkey)
        colors = {rid: self.row_color(idents[src[i]].rows[pos[i]]) for i, rid in enumerate(N.rows)}
        self.emit("move_cells", f"{label}: rows stack into one table",
                  [self.render(N, title="result", marks=m, colors=colors)])
        for rid, color in colors.items():
            self._row_color[rid] = color
        self.emit("show", label, [self.render(N, title="result", colors=colors)])
        return ni

    # ------------------------------------------------------------------ melt
    def melt(self, st: Stage, label: str) -> Ident | None:
        step = st.main
        if step.kind == "func":
            if not step.args or not isinstance(step.args[0], pd.DataFrame):
                frame_arg = step.kwargs.get("frame")
                if not isinstance(frame_arg, pd.DataFrame):
                    return None
                source, args = frame_arg, list(step.args)
            else:
                source, args = step.args[0], list(step.args[1:])
            token = st.inputs[0][1] if st.inputs else st.before_token
            name = (st.inputs[0][2] if st.inputs else st.before_name) or "df"
        else:
            source, args, token, name = st.before, list(step.args), st.before_token, st.before_name or "df"
        if not isinstance(source, pd.DataFrame) or isinstance(source.columns, pd.MultiIndex):
            return None
        kw = dict(zip(["id_vars", "value_vars", "var_name", "value_name"], args))
        kw.update({k: v for k, v in step.kwargs.items() if k != "frame"})
        id_vars = kw.get("id_vars")
        id_vars = [] if id_vars is None else ([id_vars] if not isinstance(id_vars, (list, tuple)) else list(id_vars))
        aug_kw = dict(kw, id_vars=id_vars + ["__rid"])
        if kw.get("value_vars") is None:
            aug_kw["value_vars"] = [c for c in source.columns if c not in id_vars]
        aug = source.assign(__rid=np.arange(len(source))).melt(**aug_kw)
        after = st.after
        if not isinstance(after, pd.DataFrame) or len(aug) != len(after):
            return None
        var_name = kw.get("var_name") or "variable"
        rids = [int(x) for x in aug["__rid"]]
        variables = list(aug[var_name])

        pv = view_of(source)
        Pi = self.ident_for(token, pv, name)
        P = tdata(pv, Pi)
        pcol = {str(c): Pi.cols[i] for i, c in enumerate(source.columns)}
        value_cids = [pcol[str(v)] for v in dict.fromkeys(variables) if str(v) in pcol]
        id_cids = [pcol[str(v)] for v in id_vars if str(v) in pcol]
        self.emit("move_cells", f"{label}: value columns will become rows",
                  [self.render(P, title=name, marks=Marks(cols={**{c: "source" for c in value_cids},
                                                                **{c: "focus" for c in id_cids}}))])

        nv = view_of(after)
        prefix = f"t{st.index}"
        reuse = {str(v): pcol[str(v)] for v in id_vars if str(v) in pcol}
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], self._col_ids(nv.names, prefix, reuse))
        N = tdata(nv, ni)
        value_name = kw.get("value_name") or "value"
        ncol = {N.names[c]: c for c in N.cols}
        m = Marks()
        used: set[str] = set()
        for i, rid in enumerate(N.rows):
            srid = Pi.rows[rids[i]]
            src_col = pcol.get(str(variables[i]))
            for cid in N.cols:
                nm = N.names[cid]
                if nm == str(value_name) and src_col:
                    key = C.cell_key(srid, src_col)
                elif nm == str(var_name) and src_col:
                    m.origins[(rid, cid)] = C.header_key("main", src_col)
                    m.cells[(rid, cid)] = "new"
                    continue
                elif nm in pcol:
                    key = C.cell_key(srid, pcol[nm])
                else:
                    continue
                if key in used:
                    m.origins[(rid, cid)] = key
                else:
                    m.cell_keys[(rid, cid)] = key
                    used.add(key)
            m.badge_origins[rid] = C.badge_key(srid)
        del ncol
        colors = {rid: self.row_color(Pi.rows[rids[i]]) for i, rid in enumerate(N.rows)}
        self._row_color.update(colors)
        self.emit("move_cells", f"{label}: each value cell moves to its own row",
                  [self.render(N, title=name, marks=m)])
        self.emit("show", label, [self.render(N, title=name)])
        return ni

    # ------------------------------------------------------------------ pivot / pivot_table
    def pivot(self, st: Stage, label: str) -> Ident | None:
        step = st.main
        source = st.before
        if step.kind == "func":
            source = step.args[0] if step.args and isinstance(step.args[0], pd.DataFrame) else step.kwargs.get("data")
        if not isinstance(source, pd.DataFrame):
            return None
        names = ["values", "index", "columns"] if step.name == "pivot_table" else []
        args = list(step.args[1:] if step.kind == "func" else step.args)
        kw = dict(zip(names, args))
        kw.update(step.kwargs)
        index, columns, values = kw.get("index"), kw.get("columns"), kw.get("values")
        if not isinstance(index, str) or not isinstance(columns, str):
            return None
        after = st.after
        if not isinstance(after, pd.DataFrame):
            return None
        value_cols = [values] if isinstance(values, str) else (list(values) if values is not None else
                                                               [c for c in source.columns if c not in (index, columns)])
        multi = isinstance(after.columns, pd.MultiIndex)
        token = st.inputs[0][1] if step.kind == "func" and st.inputs else st.before_token
        name = (st.inputs[0][2] if step.kind == "func" and st.inputs else st.before_name) or "df"
        pv = view_of(source)
        Pi = self.ident_for(token, pv, name)
        P = tdata(pv, Pi)
        pcol = {str(c): Pi.cols[i] for i, c in enumerate(source.columns)}
        nv = view_of(after)
        prefix = f"p{st.index}"
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], self._col_ids(nv.names, prefix, {}))
        N = tdata(nv, ni)
        targets: dict[tuple[str, str], list[str]] = {}
        badge_sources: dict[str, list[str]] = {}
        header_sources: dict[str, list[str]] = {}
        for p in range(len(source)):
            rk, ck = source[index].iloc[p], source[columns].iloc[p]
            try:
                r = after.index.get_loc(rk)
            except KeyError:
                continue
            if not isinstance(r, int):
                continue
            srid = Pi.rows[p]
            badge_sources.setdefault(ni.rows[r], []).append(C.cell_key(srid, pcol[str(index)]))
            for v in value_cols:
                try:
                    c = after.columns.get_loc((v, ck) if multi else ck)
                except KeyError:
                    continue
                if not isinstance(c, int):
                    continue
                targets.setdefault((ni.rows[r], ni.cols[c]), []).append(C.cell_key(srid, pcol[str(v)]))
                header_sources.setdefault(ni.cols[c], []).append(C.cell_key(srid, pcol[str(columns)]))
        m = Marks()
        ghosts: list[dict] = []
        for (rid, cid), keys in targets.items():
            m.cell_keys[(rid, cid)] = keys[0]
            m.cells[(rid, cid)] = "changed" if len(keys) > 1 else None  # type: ignore[assignment]
            target = C.cell_key(rid, cid)
            ghosts += [C.ghost(k, target) for k in keys[1:]]
        m.cells = {k: v for k, v in m.cells.items() if v}
        for rid, keys in badge_sources.items():
            ghosts += [C.ghost(k, C.badge_key(rid)) for k in keys]
        for cid, keys in header_sources.items():
            ghosts += [C.ghost(k, C.header_key("main", cid)) for k in keys]
        focus = Marks(cols={pcol[str(index)]: "focus", pcol[str(columns)]: "focus",
                            **{pcol[str(v)]: "source" for v in value_cols if str(v) in pcol}})
        self.emit("move_cells", f"{label}: '{index}' becomes rows, '{columns}' becomes columns",
                  [self.render(P, title=name, marks=focus)])
        self.emit("move_cells", f"{label}: values move into the grid",
                  [self.render(N, title=name, marks=m, ghosts=ghosts)])
        self.emit("show", label, [self.render(N, title=name)])
        return ni

    # ------------------------------------------------------------------ stack / unstack
    def stack(self, st: Stage, label: str) -> Ident | None:
        source, after = st.before, st.after
        if not isinstance(source, pd.DataFrame) or not isinstance(after, pd.Series):
            return None
        if not isinstance(after.index, pd.MultiIndex) or after.index.nlevels != 2:
            return None
        pv = view_of(source)
        Pi = self.ident_for(st.before_token, pv, st.before_name or "df")
        P = tdata(pv, Pi)
        rpos = {lab: i for i, lab in enumerate(source.index)}
        cpos = {str(c): i for i, c in enumerate(source.columns)}
        nv = view_of(after)
        prefix = f"k{st.index}"
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], [f"{prefix}.value"])
        N = tdata(nv, ni)
        m = Marks()
        for i, (r, c) in enumerate(after.index):
            if r not in rpos or str(c) not in cpos:
                return None
            srid, scid = Pi.rows[rpos[r]], Pi.cols[cpos[str(c)]]
            m.cell_keys[(ni.rows[i], ni.cols[0])] = C.cell_key(srid, scid)
            m.badge_origins[ni.rows[i]] = C.header_key("main", scid)
        self.emit("move_cells", f"{label}: columns fold down into the index", [self.render(P)])
        self.emit("move_cells", f"{label}: every cell becomes a row", [self.render(N, marks=m)])
        self.emit("show", label, [self.render(N)])
        return ni

    def unstack(self, st: Stage, label: str) -> Ident | None:
        source, after = st.before, st.after
        if not isinstance(source, pd.Series) or not isinstance(after, pd.DataFrame):
            return None
        if not isinstance(source.index, pd.MultiIndex) or source.index.nlevels != 2:
            return None
        pv = view_of(source)
        Pi = self.ident_for(st.before_token, pv, st.before_name or "s")
        P = tdata(pv, Pi)
        nv = view_of(after)
        prefix = f"u{st.index}"
        ni = Ident([f"{prefix}:{i}" for i in range(nv.nrows)], self._col_ids(nv.names, prefix, {}))
        N = tdata(nv, ni)
        m = Marks()
        for p, (r, c) in enumerate(source.index):
            try:
                ri, ci = after.index.get_loc(r), after.columns.get_loc(c)
            except KeyError:
                continue
            if isinstance(ri, int) and isinstance(ci, int):
                m.cell_keys[(ni.rows[ri], ni.cols[ci])] = C.cell_key(Pi.rows[p], Pi.cols[0])
        self.emit("move_cells", f"{label}: the inner index level becomes columns", [self.render(P)])
        self.emit("move_cells", f"{label}: cells spread into a grid", [self.render(N, marks=m)])
        self.emit("show", label, [self.render(N)])
        return ni


# --------------------------------------------------------------------------- labels

def main_op(st: Stage) -> str:
    s = st.main
    if s.kind == "getitem":
        return "getitem"
    return s.name


def _key_text(key: Any) -> str:
    if isinstance(key, str):
        return repr(key)
    if isinstance(key, (list, tuple)) and all(isinstance(k, str) for k in key):
        return ", ".join(repr(k) for k in key)
    return ""


def describe(st: Stage) -> str:
    s = st.main
    name = s.name
    names = st.ops
    if s.kind == "mutation":
        if name == "setitem":
            return f"Set column {s.key!r}" if s.key is not None else "Set values"
        if name.startswith("setitem_"):
            return f"Set values with .{name.split('_', 1)[1]}"
        if name.startswith("setattr_"):
            return f"Replace .{name.split('_', 1)[1]}"
        if name == "delitem":
            return "Delete column"
        return f".{name}(...) in place"
    if s.kind == "getitem":
        key = s.key
        if isinstance(key, (pd.Series, np.ndarray, list)) and len(key) and pd.api.types.is_bool_dtype(pd.Series(list(key))):
            return "Keep rows where the condition is True"
        if "loc" in names:
            return "Select with .loc[...]"
        if "iloc" in names:
            return "Select by position with .iloc[...]"
        if isinstance(key, str):
            return f"Select column {key!r}"
        if isinstance(key, list):
            return f"Select columns {_key_text(key)}"
        if isinstance(key, slice):
            return "Slice rows"
        return "Select"
    if s.kind == "binop":
        return f"Element-wise {name}"
    if s.kind == "attr":
        return f".{name}"
    if "groupby" in names and name != "groupby":
        gb = next(x for x in st.steps if x.name == "groupby")
        by = gb.args[0] if gb.args else gb.kwargs.get("by")
        what = _key_text(by) or "key"
        return f"Group by {what}, then .{name}()"
    if "rolling" in names:
        win = next(x for x in st.steps if x.name == "rolling")
        size = win.args[0] if win.args else win.kwargs.get("window")
        return f"Rolling window of {size}, then .{name}()"
    if "str" in names:
        return f"String method .str.{name}()"
    if "dt" in names:
        return f"Date method .dt.{name}"
    first = s.args[0] if s.args else None
    templates = {
        "sort_values": lambda: f"Sort by {_key_text(first if first is not None else s.kwargs.get('by'))}"
        + (" (descending)" if s.kwargs.get("ascending") is False else ""),
        "dropna": lambda: "Drop rows with missing values",
        "fillna": lambda: "Fill missing values",
        "head": lambda: f"First {first if first is not None else 5} rows",
        "tail": lambda: f"Last {first if first is not None else 5} rows",
        "query": lambda: f"Query {first!r}" if isinstance(first, str) else "Query",
        "assign": lambda: f"Add column {_key_text(list(s.kwargs))}",
        "rename": lambda: "Rename",
        "drop": lambda: "Drop",
        "nlargest": lambda: f"{first} largest by {_key_text(s.args[1] if len(s.args) > 1 else s.kwargs.get('columns'))}",
        "nsmallest": lambda: f"{first} smallest by {_key_text(s.args[1] if len(s.args) > 1 else s.kwargs.get('columns'))}",
        "astype": lambda: "Change dtype",
        "replace": lambda: "Replace values",
        "isna": lambda: "Is the value missing?",
        "isnull": lambda: "Is the value missing?",
        "duplicated": lambda: "Is the row a duplicate?",
        "drop_duplicates": lambda: "Drop duplicate rows",
        "merge": lambda: f"Merge ({s.kwargs.get('how', 'inner')})",
        "join": lambda: f"Join ({s.kwargs.get('how', 'left')})",
        "concat": lambda: "Concatenate",
        "melt": lambda: "Melt wide to long",
        "pivot": lambda: "Pivot long to wide",
        "pivot_table": lambda: "Pivot table",
        "stack": lambda: "Stack columns into rows",
        "unstack": lambda: "Unstack rows into columns",
        "value_counts": lambda: "Count each value",
        "apply": lambda: "Apply a function to each value",
        "map": lambda: "Map each value",
        "isin": lambda: "Is the value in the list?",
        "reset_index": lambda: "Reset the index",
        "set_index": lambda: "Set the index",
        "describe": lambda: "Summary statistics",
        "cumsum": lambda: "Running total",
        "shift": lambda: "Shift values",
        "rolling": lambda: "Rolling window",
    }
    if name in templates:
        return templates[name]()
    if s.kind == "func":
        return f"{name}(...)"
    if name in ("sum", "mean", "median", "min", "max", "count", "std", "nunique"):
        return f".{name}()"
    return f".{name}(...)"


def static_frames(result: Any, token_ident: Ident | None, reason: str) -> list[dict]:
    """Visual mode off: one frame with the (truncated) result."""
    gen = PandasFrameGenerator([], {})
    view = view_of(result)
    note = None
    if view.nrows > STATIC_ROWS:
        view.labels = view.labels[:STATIC_ROWS]
        view.cells = view.cells[:STATIC_ROWS]
        note = f"Showing the first {STATIC_ROWS} rows"
    ident = gen.fresh(view, "r")
    frame = C.frame("show", reason, [gen.render(tdata(view, ident), title="result", note=note)])
    return C.finalize([frame])


def too_big(values: list[Any]) -> bool:
    for v in values:
        v = as_table(v)
        if isinstance(v, pd.DataFrame) and (len(v) > MAX_ROWS or len(v.columns) > MAX_COLS):
            return True
        if isinstance(v, pd.Series) and len(v) > MAX_ROWS:
            return True
    return False


__all__ = ["PandasFrameGenerator", "view_of", "tdata", "Ident", "static_frames", "too_big", "describe", "Step"]
