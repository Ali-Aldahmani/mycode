"""Challenge validation.

A seed file is only accepted when:
  1. it matches the ChallengeSeed schema (Pydantic);
  2. the reference solution runs with real pandas and its `result` equals the
     target under the challenge's own checker options;
  3. hint 2 is a pattern with blanks (`___`), not the solution;
  4. the example code runs on the example inputs;
  5. slugs and order numbers are unique across the path.

The reference solution is executed through /pyengine, the same code the
browser runs in Pyodide, so "valid here" means "solvable there".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.core.pyengine import runner

from .schemas import ChallengeSeed


@dataclass
class Report:
    path: Path
    seed: ChallengeSeed | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.seed is not None and not self.errors


def _norm(code: str) -> str:
    return re.sub(r"\s+", "", code)


def _run(code: str, inputs: dict, run_id: str) -> tuple[bool, str]:
    res = runner.run(code, inputs, visual=True, run_id=run_id)
    if not res["ok"]:
        err = res["error"]
        return False, f"{err['type']}: {err['message']}"
    return True, ""


def validate_seed(raw: dict, path: Path) -> Report:
    report = Report(path)
    try:
        seed = ChallengeSeed.model_validate(raw)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            report.errors.append(f"{loc}: {err['msg']}")
        return report

    inputs = {k: v.model_dump() for k, v in seed.inputs.items()}
    target = seed.target.model_dump()

    run_id = f"validate:{seed.slug}"
    ok, error = _run(seed.reference_solution, inputs, run_id)
    if not ok:
        report.errors.append(f"reference_solution fails: {error}")
    else:
        verdict = runner.check(run_id, target, seed.checker_options)
        if not verdict["passed"]:
            report.errors.append(f"reference_solution does not match target: {verdict['reason']}")

    if "___" not in seed.hint_2:
        report.errors.append("hint_2 must be a pattern with blanks (___)")
    if _norm(seed.hint_2) == _norm(seed.reference_solution):
        report.errors.append("hint_2 is identical to the reference solution")
    for name in ("hint_1",):
        if _norm(getattr(seed, name)) == _norm(seed.reference_solution):
            report.errors.append(f"{name} gives away the solution")

    ex_inputs = {k: v.model_dump() for k, v in seed.example.inputs.items()}
    ok, error = _run(seed.example.code, ex_inputs, f"validate-example:{seed.slug}")
    if not ok:
        report.errors.append(f"example code fails: {error}")
    if _norm(seed.example.code) == _norm(seed.reference_solution):
        report.errors.append("the example must use different code from the solution")
    if ex_inputs == inputs:
        report.errors.append("the example must use different data from the challenge")

    if not str(seed.docs_url).startswith("https://pandas.pydata.org/"):
        report.errors.append("docs_url must point to pandas.pydata.org")

    report.seed = seed
    return report


def load_dir(directory: Path) -> list[Report]:
    reports: list[Report] = []
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            reports.append(Report(path, errors=[f"invalid JSON: {e}"]))
            continue
        reports.append(validate_seed(raw, path))

    # path-wide checks
    seen_slug: dict[str, Path] = {}
    seen_order: dict[int, Path] = {}
    for r in reports:
        if r.seed is None:
            continue
        if r.seed.slug in seen_slug:
            r.errors.append(f"duplicate slug (also in {seen_slug[r.seed.slug].name})")
        seen_slug.setdefault(r.seed.slug, r.path)
        if r.seed.order in seen_order:
            r.errors.append(f"duplicate order {r.seed.order} (also in {seen_order[r.seed.order].name})")
        seen_order.setdefault(r.seed.order, r.path)
    return reports


def valid_seeds(reports: list[Report]) -> list[ChallengeSeed]:
    return sorted((r.seed for r in reports if r.ok and r.seed is not None), key=lambda s: s.order)
