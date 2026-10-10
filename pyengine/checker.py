"""Checker "pandas_equal": compare a user's result to a challenge target.

check(output, target_spec, options) -> {"passed", "reason", "diff"}

Options (all optional):
    check_row_order     rows must be in the same order        (default False)
    check_column_order  columns must be in the same order     (default False)
    check_index         index labels must match               (default True)
    check_dtype         dtypes must match                     (default False)
    check_names         Series name / index name must match   (default False)
    rtol                relative tolerance for floats         (default 1e-6)

`diff` holds three tables in the frame-contract format: what the user
produced, the target, and a merged diff view (wrong cells, missing rows/cols
as ghosts, extra rows/cols marked).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from . import contract as C
from .pandas_frames import Ident, Marks, PandasFrameGenerator, TData, as_table, tdata, view_of
from .valuespec import build, fmt

DEFAULTS = {
    "check_row_order": False,
    "check_column_order": False,
    "check_index": True,
    "check_dtype": False,
    "check_names": False,
    "rtol": 1e-6,
}


def _kind(v: Any) -> str:
    v = as_table(v)
    if isinstance(v, pd.DataFrame):
        return "dataframe"
    if isinstance(v, pd.Series):
        return "series"
    return "scalar"


def values_equal(a: Any, b: Any, rtol: float) -> bool:
    a_missing = a is None or (not isinstance(a, (list, tuple, str)) and _isna(a))
    b_missing = b is None or (not isinstance(b, (list, tuple, str)) and _isna(b))
    if a_missing or b_missing:
        return a_missing and b_missing
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) != len(b):
            return False
        return all(values_equal(x, y, rtol) for x, y in zip(a, b))
    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return bool(a) == bool(b) and isinstance(b, (bool, np.bool_)) == isinstance(a, (bool, np.bool_))
    if isinstance(a, (int, float, np.integer, np.floating)) and isinstance(b, (int, float, np.integer, np.floating)):
        return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=1e-9)
    if isinstance(a, (np.dtype, pd.api.extensions.ExtensionDtype)) or isinstance(b, (np.dtype, pd.api.extensions.ExtensionDtype)):
        return str(a) == str(b)
    if isinstance(a, pd.Timestamp) or isinstance(b, pd.Timestamp):
        try:
            return pd.Timestamp(a) == pd.Timestamp(b)
        except (TypeError, ValueError):
            return False
    return a == b or str(a) == str(b)


def dtype_family(dtype: Any) -> str:
    """Compare types by family, not width: `astype(int)` is int32 in Pyodide
    (wasm32) and int64 on the server, and both are correct."""
    kind = getattr(dtype, "kind", "O")
    return {"i": "integer", "u": "integer", "f": "float", "b": "boolean", "M": "datetime", "m": "timedelta",
            "c": "complex"}.get(kind, "text" if str(dtype) in ("object", "str", "string") else str(dtype))


def _isna(v: Any) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _frame(v: Any) -> pd.DataFrame:
    v = as_table(v)
    if isinstance(v, pd.Series):
        return v.to_frame(name="__value__" if v.name is None else v.name)
    return v


def check(output: Any, target_spec: dict, options: dict | None = None) -> dict:
    opts = {**DEFAULTS, **(options or {})}
    target = build(target_spec)
    ok_kind, tk = _kind(output), _kind(target)
    if ok_kind != tk:
        return _result(False, f"Expected a {_kind_name(tk)} but got a {_kind_name(ok_kind)}.", output, target, opts)
    if tk == "scalar":
        passed = values_equal(_scalar(output), _scalar(target), opts["rtol"])
        reason = "" if passed else f"Expected {fmt(target)} but got {fmt(output)}."
        return _result(passed, reason, output, target, opts)
    if tk == "series" and opts["check_names"] and as_table(output).name != target.name:
        return _result(False, f"The Series should be named {target.name!r}.", output, target, opts)
    return _compare_tables(output, target, opts)


def _scalar(v: Any) -> Any:
    if isinstance(v, np.generic):
        return v.item()
    return v


def _kind_name(k: str) -> str:
    return {"dataframe": "DataFrame", "series": "Series", "scalar": "single value"}[k]


def _compare_tables(output: Any, target: Any, opts: dict) -> dict:
    o, t = _frame(output), _frame(target)
    if isinstance(output, pd.Series) and isinstance(target, pd.Series):
        o.columns = ["__value__"]
        t.columns = ["__value__"]
    rtol = opts["rtol"]
    ocols, tcols = [str(c) for c in o.columns], [str(c) for c in t.columns]
    missing_cols = [c for c in tcols if c not in ocols]
    extra_cols = [c for c in ocols if c not in tcols]
    if missing_cols or extra_cols:
        parts = []
        if missing_cols:
            parts.append(f"missing column{'s' if len(missing_cols) > 1 else ''} {', '.join(map(repr, missing_cols))}")
        if extra_cols:
            parts.append(f"unexpected column{'s' if len(extra_cols) > 1 else ''} {', '.join(map(repr, extra_cols))}")
        return _result(False, "Your result has " + " and ".join(parts) + ".", output, target, opts)
    if opts["check_column_order"] and ocols != tcols:
        return _result(False, "The columns are in the wrong order.", output, target, opts)

    if not opts["check_index"]:
        o = o.reset_index(drop=True)
        t = t.reset_index(drop=True)
    if len(o) != len(t):
        return _result(False, f"Expected {len(t)} row{'s' if len(t) != 1 else ''} but got {len(o)}.", output, target, opts)

    pairs = _align(o, t, opts)
    if pairs is None:
        return _result(False, "The rows don't match the expected rows (check the index labels).", output, target, opts)
    wrong = 0
    for oi, ti in pairs:
        for c in tcols:
            if not values_equal(o.iloc[oi][_col(o, c)], t.iloc[ti][_col(t, c)], rtol):
                wrong += 1
    if wrong:
        return _result(False, f"{wrong} value{'s are' if wrong != 1 else ' is'} different from the target.", output, target, opts)
    if opts["check_row_order"] and any(oi != ti for oi, ti in pairs):
        return _result(False, "The values are right but the rows are in the wrong order.", output, target, opts)
    if opts["check_dtype"]:
        for c in tcols:
            want, got = dtype_family(t[_col(t, c)].dtype), dtype_family(o[_col(o, c)].dtype)
            if want != got:
                return _result(False, f"Column {c!r} should hold {want} values, not {got}.", output, target, opts)
    return _result(True, "", output, target, opts)


def _col(df: pd.DataFrame, name: str) -> Any:
    for c in df.columns:
        if str(c) == name:
            return c
    raise KeyError(name)


def _align(o: pd.DataFrame, t: pd.DataFrame, opts: dict) -> list[tuple[int, int]] | None:
    """Pairs (output row, target row). By index label when labels are unique,
    otherwise by position (row order matters) or by sorted values."""
    olabels, tlabels = list(o.index), list(t.index)
    if opts["check_index"] and len(set(map(str, tlabels))) == len(tlabels) and len(set(map(str, olabels))) == len(olabels):
        opos = {str(label): i for i, label in enumerate(olabels)}
        pairs = []
        for ti, label in enumerate(tlabels):
            if str(label) not in opos:
                return None
            pairs.append((opos[str(label)], ti))
        return pairs
    if opts["check_row_order"]:
        return [(i, i) for i in range(len(t))]
    cols = [str(c) for c in t.columns]

    def order(df: pd.DataFrame) -> list[int]:
        # sort rows by their values in the *target's* column order
        ordered = [_col(df, c) for c in cols]
        return sorted(range(len(df)), key=lambda i: tuple(str(fmt(df.iloc[i][c])) for c in ordered))

    return list(zip(order(o), order(t)))


# --------------------------------------------------------------------------- diff tables

def _result(passed: bool, reason: str, output: Any, target: Any, opts: dict) -> dict:
    try:
        diff = None if passed else build_diff(output, target, opts)
    except Exception:  # noqa: BLE001 - never let the diff view break checking
        diff = None
    return {"passed": passed, "reason": reason, "diff": diff}


def build_diff(output: Any, target: Any, opts: dict) -> dict:
    gen = PandasFrameGenerator([], {})
    ov, tv = view_of(output), view_of(target)
    rtol = opts["rtol"]
    if ov.kind == "scalar" or tv.kind == "scalar":
        oi, ti = gen.fresh(ov, "u"), gen.fresh(tv, "t")
        user = gen.render(tdata(ov, oi), table_id="user", title="your result", scalar_mark="wrong")
        tgt = gen.render(tdata(tv, ti), table_id="target", title="target")
        return {"user": user, "target": tgt, "diff": None}

    ti = gen.fresh(tv, "t")
    T = tdata(tv, ti)
    # user rows take the id of the target row with the same label so colours match
    tlabel = {str(label): ti.rows[i] for i, label in enumerate(tv.labels)}
    used: set[str] = set()
    urows = []
    for i, label in enumerate(ov.labels):
        rid = tlabel.get(str(label)) if opts["check_index"] else (ti.rows[i] if i < len(ti.rows) else None)
        if rid is None or rid in used:
            rid = f"u:{i}"
        used.add(rid)
        urows.append(rid)
    tcol = {name: ti.cols[i] for i, name in enumerate(tv.names)}
    ucols = [tcol.get(name, f"u.{name}") for name in ov.names]
    U = tdata(ov, Ident(urows, ucols))

    um, tm = Marks(), Marks()
    D = T.copy()
    dm = Marks()
    target_rows = set(T.rows)
    for rid in U.rows:
        if rid not in target_rows:
            um.rows[rid] = "extra"
    for rid in T.rows:
        if rid not in set(U.rows):
            tm.rows[rid] = "missing"
            dm.rows[rid] = "missing"
    for cid in U.cols:
        if cid not in set(T.cols):
            um.cols[cid] = "extra"
    for cid in T.cols:
        if cid not in set(U.cols):
            tm.cols[cid] = "missing"
            dm.cols[cid] = "missing"
    raw_o, raw_t = _frame(output), _frame(target)
    for rid in T.rows:
        if rid not in set(U.rows):
            continue
        for cid in T.cols:
            if cid not in set(U.cols):
                continue
            uval, tval = U.cells.get((rid, cid)), T.cells.get((rid, cid))
            if uval != tval and not _close_text(uval, tval, rtol):
                um.cells[(rid, cid)] = "wrong"
                dm.cells[(rid, cid)] = "wrong"
                D.cells[(rid, cid)] = uval
            elif rid in U.rows:
                dm.cells.setdefault((rid, cid), "kept")
    del raw_o, raw_t
    # extra rows / columns go at the end of the diff view
    for rid in U.rows:
        if rid not in target_rows:
            D.rows.append(rid)
            D.labels[rid] = U.labels[rid]
            dm.rows[rid] = "extra"
            for cid in T.cols:
                D.cells[(rid, cid)] = U.cells.get((rid, cid))
    for cid in U.cols:
        if cid not in set(T.cols):
            D.cols.append(cid)
            D.names[cid] = U.names[cid]
            D.dtypes[cid] = U.dtypes[cid]
            dm.cols[cid] = "extra"
            for rid in D.rows:
                D.cells[(rid, cid)] = U.cells.get((rid, cid))
    if opts["check_row_order"]:
        order = [r for r in U.rows if r in target_rows]
        expected = [r for r in T.rows if r in set(U.rows)]
        for a, b in zip(order, expected):
            if a != b:
                um.badges[a] = "wrong"
    return {
        "user": gen.render(U, table_id="user", title="your result", marks=um),
        "target": gen.render(T, table_id="target", title="target", marks=tm),
        "diff": gen.render(D, table_id="diff", title="diff", marks=dm),
    }


def _close_text(a: str | None, b: str | None, rtol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=1e-9)
    except ValueError:
        return False


__all__ = ["check", "values_equal", "build_diff", "TData", "C"]
