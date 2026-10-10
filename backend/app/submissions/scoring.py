"""Scoring rules. The only place where points are computed.

* Every challenge starts at 100.
* Help costs points, charged once per round: example -15, hint 1 -20, hint 2 -35.
* Wrong submissions: the first two are free, then -5 each, capped at -20.
* Errors (exceptions, no `result`) are not attempts and cost nothing.
* A round ends with a correct submission; retrying after that starts a new
  round, and the best score is kept.
"""
from dataclasses import dataclass

START = 100
HELP_COSTS = {"example": 15, "hint_1": 20, "hint_2": 35}
FREE_WRONG = 2
WRONG_PENALTY = 5
WRONG_CAP = 20


@dataclass(frozen=True)
class ScoreFacts:
    status: str  # correct | wrong | error
    help_used: frozenset[str]
    wrong_before: int  # wrong submissions earlier in this round


def wrong_penalty(wrong_before: int) -> int:
    return min(WRONG_CAP, WRONG_PENALTY * max(0, wrong_before - FREE_WRONG))


def help_penalty(help_used: frozenset[str]) -> int:
    return sum(HELP_COSTS[h] for h in help_used if h in HELP_COSTS)


def score(facts: ScoreFacts) -> int | None:
    """Points for a submission; None unless it is correct."""
    if facts.status != "correct":
        return None
    return max(0, START - help_penalty(facts.help_used) - wrong_penalty(facts.wrong_before))


def potential(help_used: frozenset[str], wrong_before: int) -> int:
    """What a correct submission would score right now (shown in the UI)."""
    return max(0, START - help_penalty(help_used) - wrong_penalty(wrong_before))
