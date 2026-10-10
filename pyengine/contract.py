"""Frame contract, Python side.

This module is the single place where frames are built in Python. Its output
must match `frontend/src/engine/frames.ts` exactly (camelCase keys). Frame
generators never build raw dicts themselves; they call the helpers below.

Element keys
------------
The player identifies every visual element by a string key. When the same key
exists in two consecutive frames the element *moves*; a new key *appears*; a
missing key *fades out*. Keys are derived with the helpers in this module so
Python and TypeScript agree:

    cell     "<rowId>|<colId>"
    badge    "badge:<rowId>"            (row index label + identity colour)
    header   "hdr:<tableId>:<colId>"
    scalar   "scalar:<tableId>"
"""
from __future__ import annotations

from typing import Any, Iterable

PRIMITIVES = (
    "show",
    "fade_out",
    "slide",
    "appear",
    "scan",
    "cluster",
    "collapse",
    "connect",
    "move_cells",
)

MARKS = (
    "kept",      # green: survives / matched
    "removed",   # red: about to disappear
    "changed",   # yellow: value changed
    "new",       # green: newly created
    "focus",     # blue outline: the column(s) the operation looks at
    "source",    # blue flash: input of a scan
    "nomatch",   # gray: no partner in a join
    "wrong",     # red pulse: diff, wrong value
    "missing",   # dashed ghost: diff, row/col missing from the user's result
    "extra",     # orange: diff, row/col the target does not have
)

# Base duration of each primitive in milliseconds at 1x speed.
DURATIONS = {
    "show": 650,
    "fade_out": 800,
    "slide": 900,
    "appear": 750,
    "scan": 500,  # + SCAN_STEP per scanned row
    "cluster": 950,
    "collapse": 1100,
    "connect": 1200,
    "move_cells": 1250,
}
SCAN_STEP = 140


def cell_key(row_id: str, col_id: str) -> str:
    return f"{row_id}|{col_id}"


def badge_key(row_id: str) -> str:
    return f"badge:{row_id}"


def header_key(table_id: str, col_id: str) -> str:
    return f"hdr:{table_id}:{col_id}"


def scalar_key(table_id: str) -> str:
    return f"scalar:{table_id}"


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _maybe_list(values: list[Any] | None) -> list[Any] | None:
    if values is None or all(v is None for v in values):
        return None
    return values


def column(col_id: str, name: str, dtype: str, color: int, mark: str | None = None) -> dict:
    return _clean({"id": col_id, "name": name, "dtype": dtype, "color": color, "mark": mark})


def row(
    row_id: str,
    label: str | None,
    color: int,
    cells: list[str | None],
    *,
    mark: str | None = None,
    badge_mark: str | None = None,
    group: int | None = None,
    gap_before: bool = False,
    cell_marks: list[str | None] | None = None,
    cell_keys: list[str | None] | None = None,
    origins: list[str | None] | None = None,
    scan: list[int | None] | None = None,
    badge_key_override: str | None = None,
    badge_origin: str | None = None,
) -> dict:
    return _clean(
        {
            "id": row_id,
            "label": label,
            "color": color,
            "cells": cells,
            "mark": mark,
            "badgeMark": badge_mark,
            "group": group,
            "gapBefore": True if gap_before else None,
            "cellMarks": _maybe_list(cell_marks),
            "cellKeys": _maybe_list(cell_keys),
            "origins": _maybe_list(origins),
            "scan": _maybe_list(scan),
            "badgeKey": badge_key_override,
            "badgeOrigin": badge_origin,
        }
    )


def ghost(key: str, target: str) -> dict:
    """An element that still exists in this frame but folds into `target`.

    The player copies the element's look from the previous frame, moves it on
    top of `target` and fades it to zero. Used by collapse (groupby, reductions,
    pivot_table aggregation)."""
    return {"key": key, "target": target}


def table(
    table_id: str,
    title: str,
    kind: str,
    columns: list[dict],
    rows: list[dict],
    *,
    slot: tuple[int, int] = (0, 0),
    index_name: str | None = None,
    show_index: bool = True,
    scalar: str | None = None,
    scalar_mark: str | None = None,
    ghosts: list[dict] | None = None,
    note: str | None = None,
) -> dict:
    assert kind in ("dataframe", "series", "scalar"), kind
    return _clean(
        {
            "id": table_id,
            "title": title,
            "kind": kind,
            "slot": list(slot),
            "indexName": index_name,
            "showIndex": show_index,
            "columns": columns,
            "rows": rows,
            "scalar": scalar,
            "scalarMark": scalar_mark,
            "ghosts": ghosts or None,
            "note": note,
        }
    )


def link(link_id: str, frm: str, to: str, kind: str = "match") -> dict:
    return {"id": link_id, "from": frm, "to": to, "kind": kind}


def code_range(start_line: int, start_col: int, end_line: int, end_col: int) -> dict:
    """1-based lines and columns, end exclusive (Monaco convention)."""
    return {"startLine": start_line, "startCol": start_col, "endLine": end_line, "endCol": end_col}


def frame(
    primitive: str,
    label: str,
    tables: list[dict],
    *,
    links: list[dict] | None = None,
    code: dict | None = None,
    stage: int = 0,
    duration: int | None = None,
    scan_rows: int = 0,
) -> dict:
    assert primitive in PRIMITIVES, primitive
    if duration is None:
        duration = DURATIONS[primitive] + SCAN_STEP * scan_rows
    return {
        "index": -1,  # assigned by finalize()
        "stage": stage,
        "primitive": primitive,
        "label": label,
        "tables": tables,
        "links": links or [],
        "code": code,
        "duration": duration,
    }


def finalize(frames: Iterable[dict]) -> list[dict]:
    out = list(frames)
    for i, f in enumerate(out):
        f["index"] = i
    return out


def stage_info(index: int, label: str, op: str, code: dict | None, first: int, last: int) -> dict:
    return {"index": index, "label": label, "op": op, "code": code, "firstFrame": first, "lastFrame": last}
