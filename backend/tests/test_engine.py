"""The shared engine (/pyengine): frames, primitives, checker."""
import json

import pytest

from app.core.pyengine import checker, runner

DF = {
    "type": "dataframe",
    "columns": ["name", "city", "age", "salary"],
    "data": [
        ["Ana", "Paris", 34, 52000], ["Ben", "Lyon", 28, None], ["Cleo", "Paris", 45, 61000],
        ["Dev", "Nice", 31, 48000], ["Eli", "Lyon", None, 39000], ["Fay", "Paris", 29, 55000],
    ],
}
LEFT = {"type": "dataframe", "columns": ["emp", "dept_id"], "data": [["Ana", 1], ["Ben", 2], ["Dev", 3]]}
RIGHT = {"type": "dataframe", "columns": ["dept_id", "dept"], "data": [[1, "Sales"], [2, "IT"]]}
WIDE = {"type": "dataframe", "columns": ["student", "math", "art"], "data": [["Ana", 90, 75], ["Ben", 68, 88]]}


def prims(code, inputs=None):
    res = runner.run(code, inputs or {"df": DF}, run_id="t")
    assert res["ok"], res.get("error")
    json.dumps(res, allow_nan=False)  # the payload must be strict JSON
    return [f["primitive"] for f in res["frames"]]


@pytest.mark.parametrize(
    "code,inputs,expected",
    [
        ("result = df[df.age > 30]", None, "fade_out"),
        ("result = df.sort_values('age')", None, "slide"),
        ("result = df.fillna(0)", None, "appear"),
        ("result = df['city'].str.upper()", None, "scan"),
        ("result = df.groupby('city')['salary'].sum()", None, "collapse"),
        ("result = df.groupby('city')['salary'].sum()", None, "cluster"),
        ("result = left.merge(right, on='dept_id')", {"left": LEFT, "right": RIGHT}, "connect"),
        ("result = wide.melt(id_vars='student')", {"wide": WIDE}, "move_cells"),
    ],
)
def test_primitives(code, inputs, expected):
    assert expected in prims(code, inputs)


def test_chained_code_animates_each_stage_with_code_ranges():
    res = runner.run("result = df[df.age > 30].groupby('city')['salary'].mean()", {"df": DF}, run_id="c")
    stages = res["stages"]
    assert len(stages) == 2
    code = "result = df[df.age > 30].groupby('city')['salary'].mean()"
    first, second = stages[0]["code"], stages[1]["code"]
    assert code[first["startCol"] - 1:first["endCol"] - 1] == "[df.age > 30]"
    assert code[second["startCol"] - 1:second["endCol"] - 1] == ".groupby('city')['salary'].mean()"


def test_named_agg_keeps_and_folds_its_source_column():
    res = runner.run("result = df.groupby('city').agg(total=('salary', 'sum'), n=('salary', 'count'))",
                     {"df": DF}, run_id="n")
    frames = res["frames"]
    before = next(f for f in frames if f["primitive"] == "collapse")
    kept = frames[frames.index(before) - 1]["tables"][0]
    assert [c["name"] for c in kept["columns"]] == ["city", "salary"]
    targets = {g["target"] for g in before["tables"][0]["ghosts"] if g["key"].endswith("df.salary")}
    assert targets and all(t.endswith(".total") for t in targets)


def test_groupby_filter_shows_groups_then_drops_rows():
    p = prims("result = df.groupby('city').filter(lambda g: len(g) >= 2)")
    assert p.index("cluster") < p.index("fade_out")
    assert "collapse" not in p


def test_errors_report_the_user_line():
    res = runner.run("x = 1\nresult = df['nope']", {"df": DF}, run_id="e")
    assert res["ok"] is False
    assert res["error"]["type"] == "KeyError" and res["error"]["line"] == 2


def test_missing_result_is_an_error():
    res = runner.run("x = df.head()", {"df": DF}, run_id="e2")
    assert res["error"]["type"] == "NoResult"


def test_big_tables_skip_animation():
    big = {"type": "dataframe", "columns": ["a"], "data": [[i] for i in range(50)]}
    res = runner.run("result = df[df.a > 10]", {"df": big}, run_id="b")
    assert res["visual"] is False and len(res["frames"]) == 1


def test_checker_diff_marks_wrong_and_missing():
    runner.run("result = df[df.age > 40]", {"df": DF}, run_id="d")
    target = runner.run("result = df[df.age > 30]", {"df": DF}, run_id="d2")["result"]
    verdict = runner.check("d", target, {})
    assert verdict["passed"] is False
    marks = [r.get("mark") for r in verdict["diff"]["diff"]["rows"]]
    assert "missing" in marks


def test_checker_handles_series_and_scalars():
    assert checker.check(3.0, {"type": "scalar", "value": 3}, {})["passed"]
    assert checker.check((6, 4), {"type": "scalar", "value": [6, 4], "tuple": True}, {})["passed"]
    assert not checker.check(5, {"type": "scalar", "value": 3}, {})["passed"]
