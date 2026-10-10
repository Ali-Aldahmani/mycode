"""Value specs: the JSON format used for challenge inputs, targets and results.

    {"type": "dataframe", "columns": [...], "data": [[...], ...],
     "index": [...]?, "index_name": str?, "dtypes": {col: dtype}?}
    {"type": "series", "name": str?, "data": [...], "index": [...]?,
     "index_name": str?, "dtype": str?}
    {"type": "scalar", "value": any, "tuple": bool?}

JSON `null` means a missing value (NaN / None / NaT). Column names or index
labels given as lists become MultiIndex tuples.

This module also owns display formatting (`fmt`), so every table in the app
(stage, target, diff) prints values the same way.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- build

def _labels(values: list[Any]) -> list[Any]:
    return [tuple(v) if isinstance(v, list) else v for v in values]


def _make_index(values: list[Any], name: Any = None) -> pd.Index:
    labels = _labels(values)
    if labels and all(isinstance(v, tuple) for v in labels):
        idx = pd.MultiIndex.from_tuples(labels)
        if isinstance(name, list):
            idx.names = name
        return idx
    return pd.Index(labels, name=name)


def _apply_dtype(s: pd.Series, dtype: str) -> pd.Series:
    if dtype.startswith("datetime64"):
        return pd.to_datetime(s)
    if dtype.startswith("timedelta64"):
        return pd.to_timedelta(s)
    return s.astype(dtype)


def build(spec: dict) -> Any:
    kind = spec.get("type", "dataframe")
    if kind == "dataframe":
        columns = _labels(spec["columns"])
        if columns and all(isinstance(c, tuple) for c in columns):
            columns = pd.MultiIndex.from_tuples(columns)
        df = pd.DataFrame(spec.get("data", []), columns=columns)
        for col, dtype in (spec.get("dtypes") or {}).items():
            df[col] = _apply_dtype(df[col], dtype)
        if "index" in spec:
            df.index = _make_index(spec["index"], spec.get("index_name"))
        elif spec.get("index_name") is not None:
            df.index.name = spec["index_name"]
        if spec.get("columns_name") is not None:
            df.columns.name = spec["columns_name"]
        return df
    if kind == "series":
        s = pd.Series(spec.get("data", []), name=spec.get("name"))
        if spec.get("dtype"):
            s = _apply_dtype(s, spec["dtype"])
        if "index" in spec:
            s.index = _make_index(spec["index"], spec.get("index_name"))
        elif spec.get("index_name") is not None:
            s.index.name = spec["index_name"]
        return s
    if kind == "scalar":
        value = spec.get("value")
        if spec.get("tuple") and isinstance(value, list):
            return tuple(value)
        return value
    raise ValueError(f"Unknown value spec type: {kind!r}")


# --------------------------------------------------------------------------- dump

def _plain(v: Any) -> Any:
    """Convert a pandas/numpy scalar to a JSON-safe Python value."""
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if v is None:
        return None
    if isinstance(v, (np.dtype, pd.api.extensions.ExtensionDtype)):
        return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (pd.Timedelta, _dt.timedelta)):
        return str(v)
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


def _dump_index(idx: pd.Index) -> dict:
    out: dict[str, Any] = {}
    if not (isinstance(idx, pd.RangeIndex) and idx.start == 0 and idx.step == 1):
        out["index"] = [_plain(v) for v in idx]
    if isinstance(idx, pd.MultiIndex):
        if any(n is not None for n in idx.names):
            out["index_name"] = list(idx.names)
    elif idx.name is not None:
        out["index_name"] = _plain(idx.name)
    return out


def _special_dtype(dtype: Any) -> str | None:
    s = str(dtype)
    if s.startswith(("datetime64", "timedelta64")) or s in ("category", "bool", "boolean", "Int64", "Float64"):
        return s
    return None


def dump(value: Any) -> dict:
    if isinstance(value, pd.DataFrame):
        spec: dict[str, Any] = {
            "type": "dataframe",
            "columns": [_plain(c) for c in value.columns],
            "data": [[_plain(x) for x in row] for row in value.astype(object).itertuples(index=False, name=None)],
        }
        dtypes = {str(c): _special_dtype(t) for c, t in value.dtypes.items() if _special_dtype(t)}
        if dtypes and not isinstance(value.columns, pd.MultiIndex):
            spec["dtypes"] = dtypes
        spec.update(_dump_index(value.index))
        if value.columns.name is not None:
            spec["columns_name"] = _plain(value.columns.name)
        return spec
    if isinstance(value, pd.Series):
        spec = {"type": "series", "name": _plain(value.name), "data": [_plain(x) for x in value.astype(object)]}
        special = _special_dtype(value.dtype)
        if special:
            spec["dtype"] = special
        spec.update(_dump_index(value.index))
        return spec
    if isinstance(value, pd.Index):
        return dump(pd.Series(value, name=value.name))
    if isinstance(value, np.ndarray) and value.ndim == 1:
        return dump(pd.Series(value))
    if isinstance(value, tuple):
        return {"type": "scalar", "value": [_plain(v) for v in value], "tuple": True}
    if isinstance(value, list):
        return {"type": "scalar", "value": [_plain(v) for v in value]}
    return {"type": "scalar", "value": _plain(value)}


# --------------------------------------------------------------------------- display

def fmt_float(x: float) -> str:
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    if x.is_integer() and abs(x) < 1e15:
        return f"{x:.1f}"
    if abs(x) >= 1e6 or abs(x) < 1e-4:
        return f"{x:.4g}"
    return f"{x:.4f}".rstrip("0")


def fmt(v: Any) -> str | None:
    """Display text for one value. None means "missing" (rendered gray NaN)."""
    if v is None:
        return None
    if isinstance(v, (np.dtype, pd.api.extensions.ExtensionDtype)):
        return str(v)
    if isinstance(v, (list, tuple)):
        inner = ", ".join("NaN" if fmt(x) is None else str(fmt(x)) for x in v)
        return f"({inner})" if isinstance(v, tuple) else f"[{inner}]"
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (bool, np.bool_)):
        return "True" if v else "False"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return fmt_float(float(v))
    if isinstance(v, pd.Timestamp):
        if v.hour == v.minute == v.second == 0 and v.microsecond == 0 and v.tzinfo is None:
            return v.strftime("%Y-%m-%d")
        return str(v)
    return str(v)


def fmt_label(v: Any) -> str | None:
    if isinstance(v, tuple):
        return ", ".join("NaN" if fmt(x) is None else str(fmt(x)) for x in v)
    return fmt(v)


def col_name(c: Any) -> str:
    if isinstance(c, tuple):
        return " ".join(str(x) for x in c if str(x) != "")
    return "" if c is None else str(c)
