"""Entry points called from the browser worker (and from backend tests).

run_json(request_json) -> response_json
    request:  {"runId", "code", "inputs": {name: valuespec}, "visualType"?, "visual"?: bool}
    response: {"ok": true, "runId", "frames", "stages", "visual", "note"?, "output", "stdout", "ms"}
            | {"ok": false, "runId", "error": {"type", "message", "line"}, "stdout", "ms"}

check_json(request_json) -> response_json
    request:  {"runId", "target": valuespec, "options"?: {...}}
    response: {"passed", "reason", "diff"}

The user's result for each run is kept in memory (last few runs) so the
checker can compare the real pandas object, not its JSON rendering.
"""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from . import checker
from .pandas_frames import PandasFrameGenerator, static_frames, tdata, too_big, view_of
from .tracer import UserCodeError, displayable, run_traced
from .valuespec import build, dump

# Frame generators by library. A new family (e.g. Python loop tracing) adds an
# entry here; the player on the TypeScript side does not change.
GENERATORS = {"pandas": PandasFrameGenerator}

_RESULTS: "OrderedDict[str, Any]" = OrderedDict()
_KEEP = 8


def prepare_inputs(specs: dict[str, dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, spec in specs.items():
        value = build(spec)
        if isinstance(value, pd.DataFrame) and "index" not in spec:
            value = value.reset_index(drop=True)  # clean RangeIndex = row identity
        out[name] = value
    return out


def run(code: str, input_specs: dict[str, dict], *, visual_type: str | None = None, visual: bool = True,
        run_id: str = "", library: str = "pandas") -> dict:
    started = time.perf_counter()
    inputs = prepare_inputs(input_specs)
    tracer = None
    try:
        tracer, ns = run_traced(code, {k: v.copy() if hasattr(v, "copy") else v for k, v in inputs.items()})
        if "result" not in ns:
            raise UserCodeError("NoResult", "Your code must assign the answer to a variable named `result`.", None)
        result = ns["result"]
        if not displayable(result) or callable(result):
            raise UserCodeError(
                "BadResult",
                f"`result` must be a DataFrame, a Series or a value, not {type(result).__name__}.",
                None,
            )
    except UserCodeError as e:
        return {
            "ok": False,
            "runId": run_id,
            "error": e.as_dict(),
            "stdout": tracer.stdout.getvalue() if tracer else "",
            "ms": round((time.perf_counter() - started) * 1000, 1),
        }

    stages = tracer.stages
    values = list(inputs.values()) + [s.after for s in stages] + [result]
    note = None
    if not visual or too_big(values):
        note = "Visual mode is off for tables with more than 20 rows." if visual else None
        frames = static_frames(result, None, "Result")
        infos: list[dict] = []
        is_visual = False
    else:
        gen = GENERATORS.get(library, PandasFrameGenerator)(stages, inputs, visual_type)
        frames, infos = gen.generate(result, tracer.token_of(result))
        is_visual = True

    _RESULTS[run_id] = result
    while len(_RESULTS) > _KEEP:
        _RESULTS.popitem(last=False)

    out_gen = PandasFrameGenerator([], {})
    out_view = view_of(result)
    output = out_gen.render(tdata(out_view, out_gen.fresh(out_view, "out")), table_id="output", title="result")
    return {
        "ok": True,
        "runId": run_id,
        "frames": frames,
        "stages": infos,
        "visual": is_visual,
        "note": note,
        "output": output,
        "result": dump(result),
        "stdout": tracer.stdout.getvalue(),
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


def render_specs(specs: dict[str, dict], *, reset_index: bool = True) -> list[dict]:
    """Static tables (frame-contract format) for named value specs, formatted
    exactly like the stage. Used for the Description tab and the target."""
    gen = PandasFrameGenerator([], {})
    tables = []
    values = prepare_inputs(specs) if reset_index else {k: build(v) for k, v in specs.items()}
    for i, (name, value) in enumerate(values.items()):
        view = view_of(value)
        tables.append(gen.render(tdata(view, gen.fresh(view, name)), table_id=f"in{i}", title=name, slot=(i, 0)))
    return tables


def check(run_id: str, target: dict, options: dict | None = None) -> dict:
    if run_id not in _RESULTS:
        return {"passed": False, "reason": "Run the code first.", "diff": None}
    return checker.check(_RESULTS[run_id], target, options)


def run_json(request_json: str) -> str:
    req = json.loads(request_json)
    res = run(
        req["code"],
        req.get("inputs", {}),
        visual_type=req.get("visualType"),
        visual=req.get("visual", True),
        run_id=req.get("runId", ""),
        library=req.get("library", "pandas"),
    )
    return json.dumps(res, allow_nan=False, default=str)


def check_json(request_json: str) -> str:
    req = json.loads(request_json)
    return json.dumps(check(req["runId"], req["target"], req.get("options")), allow_nan=False, default=str)
