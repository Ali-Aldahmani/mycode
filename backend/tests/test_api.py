def submit(client, status, slug="filter-age", **kw):
    body = {"challenge_slug": slug, "code": "result = df", "status": status, **kw}
    return client.post("/submissions", json=body)


def test_path_unlocks_in_order(client):
    path = client.get("/challenges").json()
    assert [c["slug"] for c in path] == ["filter-age", "sort-age"]
    assert [c["locked"] for c in path] == [False, True]
    assert submit(client, "correct", slug="sort-age").status_code == 403


def test_detail_hides_solution_until_submitted(client):
    d = client.get("/challenges/filter-age", params={"include_solution": True}).json()
    assert d["reference_solution"] is None
    assert d["costs"] == {"example": 15, "hint_1": 20, "hint_2": 35}
    assert d["next_slug"] == "sort-age" and d["prev_slug"] is None
    assert d["potential"] == 100
    submit(client, "wrong")
    d = client.get("/challenges/filter-age", params={"include_solution": True}).json()
    assert d["reference_solution"] == "result = df[df['age'] > 30]"
    assert client.get("/challenges/filter-age").json()["reference_solution"] is None


def test_errors_are_not_attempts(client):
    r = submit(client, "error", error="KeyError: 'x'").json()
    assert r["submission"]["attempt_number"] is None
    assert r["submission"]["score"] is None
    r = submit(client, "correct").json()
    assert r["submission"]["attempt_number"] == 1
    assert r["submission"]["score"] == 100


def test_wrong_attempts_and_help_reduce_score(client):
    for _ in range(3):
        submit(client, "wrong")
    assert client.post("/progress/filter-age/help", json={"kind": "hint_1"}).json() == {"help_used": ["hint_1"], "cost": 20}
    # opening the same hint again is free
    assert client.post("/progress/filter-age/help", json={"kind": "hint_1"}).json()["cost"] == 0
    assert client.get("/challenges/filter-age").json()["potential"] == 75
    r = submit(client, "correct", used_example=True).json()
    sub = r["submission"]
    assert sub["score"] == 100 - 20 - 15 - 5
    assert sub["attempt_number"] == 4
    assert sub["hints_used"] == ["example", "hint_1"]
    assert r["progress"]["best_score"] == 60
    assert r["progress"]["solved"] is True
    assert r["unlocked_next"] is True and r["next_slug"] == "sort-age"
    assert client.get("/challenges").json()[1]["locked"] is False


def test_retry_starts_a_new_round_and_keeps_best(client):
    submit(client, "correct", used_hint_2=True)  # 65
    r = submit(client, "correct").json()  # fresh round, no help
    assert r["submission"]["score"] == 100
    assert r["submission"]["round"] == 2
    assert r["progress"]["best_score"] == 100
    r = submit(client, "correct", used_hint_1=True).json()
    assert r["progress"]["best_score"] == 100


def test_history_and_progress(client):
    submit(client, "wrong")
    submit(client, "correct")
    hist = client.get("/challenges/filter-age/submissions").json()
    assert [h["status"] for h in hist] == ["correct", "wrong"]
    p = client.get("/progress").json()
    assert p["overall"] == {"solved": 1, "total": 2, "total_score": 100, "average": 100.0}
    assert p["categories"] == [{"level": 2, "category": "Pick", "solved": 1, "total": 2, "average": 100.0}]
