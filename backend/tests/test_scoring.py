from app.submissions.scoring import ScoreFacts, potential, score


def facts(status="correct", help_used=(), wrong=0):
    return ScoreFacts(status=status, help_used=frozenset(help_used), wrong_before=wrong)


def test_clean_solve_scores_100():
    assert score(facts()) == 100


def test_help_costs_add_up():
    assert score(facts(help_used=["example"])) == 85
    assert score(facts(help_used=["hint_1"])) == 80
    assert score(facts(help_used=["hint_2"])) == 65
    assert score(facts(help_used=["example", "hint_1", "hint_2"])) == 30


def test_first_two_wrong_are_free_then_5_each_capped_at_20():
    assert [score(facts(wrong=w)) for w in range(0, 9)] == [100, 100, 100, 95, 90, 85, 80, 80, 80]


def test_only_correct_submissions_score():
    assert score(facts(status="wrong")) is None
    assert score(facts(status="error")) is None


def test_never_negative():
    assert score(facts(help_used=["example", "hint_1", "hint_2"], wrong=50)) == 10
    assert potential(frozenset({"example", "hint_1", "hint_2"}), 50) == 10
