from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.challenges.models import Challenge
from app.progress import service as progress_service
from app.users.models import User

from . import scoring
from .models import Submission
from app.progress.schemas import ChallengeProgressOut

from .schemas import SubmissionIn, SubmissionOut, SubmissionResult


def current_round(db: Session, user: User, challenge: Challenge) -> int:
    """Round number = 1 + number of correct submissions so far."""
    solved = db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.user_id == user.id,
            Submission.challenge_id == challenge.id,
            Submission.status == "correct",
        )
    )
    return 1 + int(solved or 0)


def round_counts(db: Session, user: User, challenge: Challenge, round_no: int) -> tuple[int, int]:
    """(wrong submissions, counted attempts) in a round."""
    rows = db.execute(
        select(Submission.status, func.count())
        .where(Submission.user_id == user.id, Submission.challenge_id == challenge.id, Submission.round == round_no)
        .group_by(Submission.status)
    ).all()
    counts = {status: n for status, n in rows}
    wrong = int(counts.get("wrong", 0))
    return wrong, wrong + int(counts.get("correct", 0))


def create(db: Session, user: User, data: SubmissionIn) -> SubmissionResult:
    challenge = db.scalar(select(Challenge).where(Challenge.slug == data.challenge_slug))
    if challenge is None:
        raise HTTPException(404, f"Unknown challenge {data.challenge_slug!r}")
    path = list(db.scalars(select(Challenge).order_by(Challenge.order)))
    progress = progress_service.progress_map(db, user)
    if challenge.id not in progress_service.unlocked_ids(path, progress):
        raise HTTPException(403, "This challenge is locked. Finish the previous one first.")

    p = progress_service.get_or_create(db, user, challenge)
    round_no = current_round(db, user, challenge)
    wrong_before, attempts_before = round_counts(db, user, challenge, round_no)
    # help: what the server recorded for this round, plus what the browser reports
    help_used = set(p.help_used or [])
    for flag, name in ((data.used_example, "example"), (data.used_hint_1, "hint_1"), (data.used_hint_2, "hint_2")):
        if flag:
            help_used.add(name)
    facts = scoring.ScoreFacts(status=data.status, help_used=frozenset(help_used), wrong_before=wrong_before)
    points = scoring.score(facts)

    sub = Submission(
        user_id=user.id,
        challenge_id=challenge.id,
        code=data.code,
        status=data.status,
        score=points,
        hints_used=sorted(help_used),
        used_example="example" in help_used,
        used_hint_1="hint_1" in help_used,
        used_hint_2="hint_2" in help_used,
        attempt_number=None if data.status == "error" else attempts_before + 1,
        round=round_no,
        error=data.error,
        reason=data.reason,
        runtime_ms=data.runtime_ms,
    )
    db.add(sub)

    unlocked_next = False
    next_challenge = next((c for c in path if c.order > challenge.order), None)
    if data.status == "correct":
        p.solved = True
        p.unlocked = True
        p.best_score = max(p.best_score or 0, points or 0)
        if p.solved_at is None:
            p.solved_at = sub.created_at
        p.help_used = []  # the next try is a fresh round
        if next_challenge is not None:
            np = progress_service.get_or_create(db, user, next_challenge)
            if not np.unlocked:
                np.unlocked = True
                unlocked_next = True
    else:
        p.help_used = sorted(help_used)
    db.commit()
    db.refresh(sub)
    db.refresh(p)

    after_wrong = wrong_before + (1 if data.status == "wrong" else 0)
    potential = scoring.potential(frozenset() if data.status == "correct" else frozenset(help_used),
                                  0 if data.status == "correct" else after_wrong)
    return SubmissionResult(
        submission=SubmissionOut.model_validate(sub),
        progress=ChallengeProgressOut.model_validate(p),
        overall=progress_service.overview(db, user).overall,
        potential=potential,
        next_slug=next_challenge.slug if next_challenge else None,
        unlocked_next=unlocked_next,
    )


def history(db: Session, user: User, challenge: Challenge) -> list[Submission]:
    return list(
        db.scalars(
            select(Submission)
            .where(Submission.user_id == user.id, Submission.challenge_id == challenge.id)
            .order_by(Submission.created_at.desc(), Submission.id.desc())
        )
    )


def has_submitted(db: Session, user: User, challenge: Challenge) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.user_id == user.id, Submission.challenge_id == challenge.id, Submission.status != "error"
            )
        )
    )
