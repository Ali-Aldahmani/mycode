from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.challenges import service as challenge_service
from app.core.db import get_db
from app.submissions import scoring
from app.users.deps import current_user
from app.users.models import User

from . import service
from .schemas import HelpIn, HelpOut, ProgressOut

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.overview(db, user)


@router.post("/{slug}/help", response_model=HelpOut)
def open_help(slug: str, data: HelpIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Record that a hint/example was opened, so its cost survives a reload.
    Each kind is charged once per round."""
    if data.kind not in scoring.HELP_COSTS:
        raise HTTPException(422, f"kind must be one of {sorted(scoring.HELP_COSTS)}")
    challenge = challenge_service.get_by_slug(db, slug)
    p = service.get_or_create(db, user, challenge)
    used = set(p.help_used or [])
    cost = 0 if data.kind in used else scoring.HELP_COSTS[data.kind]
    used.add(data.kind)
    p.help_used = sorted(used)
    db.commit()
    return HelpOut(help_used=p.help_used, cost=cost)
