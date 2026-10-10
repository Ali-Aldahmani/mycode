from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.progress import service as progress_service
from app.submissions import scoring
from app.submissions import service as submission_service
from app.users.models import User

from .models import Challenge
from .schemas import ChallengeDetail, ChallengeSeed, ChallengeSummary, Costs, DisplayTables

_display_cache: dict[tuple[int, str], DisplayTables] = {}


def display_tables(c: Challenge) -> DisplayTables:
    from app.core.pyengine import runner

    key = (c.id, str(c.updated_at))
    if key not in _display_cache:
        target = runner.render_specs({"target": c.target}, reset_index=False)[0]
        target["id"] = "target"
        _display_cache[key] = DisplayTables(
            inputs=runner.render_specs(c.inputs),
            target=target,
            example_inputs=runner.render_specs(c.example.get("inputs", {})),
        )
    return _display_cache[key]


def path(db: Session) -> list[Challenge]:
    return list(db.scalars(select(Challenge).order_by(Challenge.order)))


def get_by_slug(db: Session, slug: str) -> Challenge:
    c = db.scalar(select(Challenge).where(Challenge.slug == slug))
    if c is None:
        raise HTTPException(404, f"Unknown challenge {slug!r}")
    return c


def list_path(db: Session, user: User) -> list[ChallengeSummary]:
    items = path(db)
    progress = progress_service.progress_map(db, user)
    open_ids = progress_service.unlocked_ids(items, progress)
    out = []
    for c in items:
        p = progress.get(c.id)
        out.append(
            ChallengeSummary(
                id=c.id,
                slug=c.slug,
                order=c.order,
                level=c.level,
                title=c.title,
                method=c.method,
                category=c.category,
                locked=c.id not in open_ids,
                solved=bool(p and p.solved),
                best_score=p.best_score if p else None,
            )
        )
    return out


def detail(db: Session, user: User, slug: str, include_solution: bool) -> ChallengeDetail:
    c = get_by_slug(db, slug)
    items = path(db)
    progress = progress_service.progress_map(db, user)
    p = progress.get(c.id)
    pos = next(i for i, x in enumerate(items) if x.id == c.id)
    submitted = submission_service.has_submitted(db, user, c)
    help_used = frozenset(p.help_used or []) if p else frozenset()
    wrong, _ = submission_service.round_counts(db, user, c, submission_service.current_round(db, user, c))
    return ChallengeDetail(
        id=c.id,
        slug=c.slug,
        order=c.order,
        level=c.level,
        title=c.title,
        method=c.method,
        category=c.category,
        language=c.language,
        library=c.library,
        source=c.source,
        task=c.task,
        inputs=c.inputs,
        target=c.target,
        starter_code=c.starter_code,
        hint_1=c.hint_1,
        hint_2=c.hint_2,
        example=c.example,
        why=c.why,
        docs_url=c.docs_url,
        checker_type=c.checker_type,
        checker_options=c.checker_options or {},
        visual_type=c.visual_type,
        costs=Costs(**scoring.HELP_COSTS),
        locked=c.id not in progress_service.unlocked_ids(items, progress),
        solved=bool(p and p.solved),
        best_score=p.best_score if p else None,
        submitted=submitted,
        prev_slug=items[pos - 1].slug if pos > 0 else None,
        next_slug=items[pos + 1].slug if pos + 1 < len(items) else None,
        total=len(items),
        help_used=sorted(help_used),
        potential=scoring.potential(help_used, wrong),
        display=display_tables(c),
        reference_solution=c.reference_solution if include_solution and submitted else None,
    )


def upsert(db: Session, seeds: list[ChallengeSeed]) -> tuple[int, int]:
    """Insert or update challenges by slug. Returns (created, updated)."""
    created = updated = 0
    existing = {c.slug: c for c in db.scalars(select(Challenge))}
    # free the unique `order` values first so challenges can be reordered
    for c in existing.values():
        c.order = -c.id
    db.flush()
    for seed in seeds:
        fields = seed.db_fields()
        c = existing.get(seed.slug)
        if c is None:
            db.add(Challenge(**fields))
            created += 1
        else:
            for k, v in fields.items():
                setattr(c, k, v)
            updated += 1
    db.flush()
    seeded = {s.slug for s in seeds}
    for slug, c in existing.items():
        if slug not in seeded:
            db.delete(c)  # removed from /challenges
    db.commit()
    return created, updated
