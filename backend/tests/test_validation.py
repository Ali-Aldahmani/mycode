import json
from pathlib import Path

from app.challenges.validation import load_dir, validate_seed

from .conftest import seed


def check(raw):
    return validate_seed(raw, Path("x.json"))


def test_valid_seed_passes():
    r = check(seed())
    assert r.ok, r.errors


def test_wrong_target_is_rejected():
    bad = seed(target={"type": "dataframe", "columns": ["name", "age"], "data": [["Ana", 34]], "index": [0]})
    r = check(bad)
    assert not r.ok
    assert any("does not match target" in e for e in r.errors)


def test_broken_solution_is_rejected():
    r = check(seed(reference_solution="result = df['nope']"))
    assert any("reference_solution fails" in e for e in r.errors)


def test_hint_2_must_not_be_the_solution():
    r = check(seed(hint_2="result = df[df['age'] > 30]"))
    assert any("blanks" in e for e in r.errors) or any("identical" in e for e in r.errors)


def test_schema_errors_are_reported():
    r = check(seed(order=0, visual_type="explode"))
    assert not r.ok and len(r.errors) == 2


def test_sort_challenge_requires_row_order():
    raw = seed(
        reference_solution="result = df.sort_values('age')",
        target={"type": "dataframe", "columns": ["name", "age"], "data": [["Ben", 28], ["Ana", 34], ["Cleo", 45]], "index": [1, 0, 2]},
        checker_options={"check_row_order": True},
    )
    assert check(raw).ok
    raw["target"] = {"type": "dataframe", "columns": ["name", "age"], "data": [["Ana", 34], ["Ben", 28], ["Cleo", 45]]}
    assert not check(raw).ok


def test_duplicate_slugs_are_rejected(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(seed()))
    (tmp_path / "b.json").write_text(json.dumps(seed(order=2)))
    reports = load_dir(tmp_path)
    assert sum(r.ok for r in reports) == 1


def test_every_repo_challenge_is_valid():
    """The real seed files must all pass."""
    from app.core.config import settings

    reports = load_dir(settings.challenges_dir)
    bad = {r.path.name: r.errors for r in reports if not r.ok}
    assert not bad, bad
