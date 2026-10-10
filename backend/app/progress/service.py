from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.challenges.models import Challenge
from app.users.models import User

from .models import Progress
from .schemas import CategoryProgress, OverallProgress, ProgressOut


def progress_map(db: Session, user: User) -> dict[int, Progress]:
    rows = db.scalars(select(Progress).where(Progress.user_id == user.id))
    return {p.challenge_id: p for p in rows}


def get_or_create(db: Session, user: User, challenge: Challenge) -> Progress:
    p = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.challenge_id == challenge.id))
    if p is None:
        p = Progress(user_id=user.id, challenge_id=challenge.id, solved=False, unlocked=False, help_used=[])
        db.add(p)
        db.flush()
    return p


def unlocked_ids(path: list[Challenge], progress: dict[int, Progress]) -> set[int]:
    """The first challenge is always open; solving one opens the next."""
    out: set[int] = set()
    prev_solved = True
    for c in path:
        p = progress.get(c.id)
        if prev_solved or (p is not None and (p.unlocked or p.solved)):
            out.add(c.id)
        prev_solved = p is not None and p.solved
    return out


def overview(db: Session, user: User) -> ProgressOut:
    path = list(db.scalars(select(Challenge).order_by(Challenge.order)))
    progress = progress_map(db, user)
    groups: dict[tuple[int, str], list[Challenge]] = defaultdict(list)
    for c in path:
        groups[(c.level, c.category)].append(c)

    def avg(scores: list[int]) -> float | None:
        return round(sum(scores) / len(scores), 1) if scores else None

    categories = []
    for (level, category), items in sorted(groups.items()):
        scores = [progress[c.id].best_score for c in items if c.id in progress and progress[c.id].best_score is not None]
        solved = sum(1 for c in items if c.id in progress and progress[c.id].solved)
        categories.append(CategoryProgress(level=level, category=category, solved=solved, total=len(items), average=avg(scores)))  # type: ignore[arg-type]
    all_scores = [p.best_score for p in progress.values() if p.best_score is not None]
    overall = OverallProgress(
        solved=sum(1 for p in progress.values() if p.solved),
        total=len(path),
        total_score=sum(all_scores),
        average=avg(all_scores),
    )
    return ProgressOut(overall=overall, categories=categories)
