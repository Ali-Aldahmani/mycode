from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.submissions import service as submission_service
from app.submissions.schemas import SubmissionOut
from app.users.deps import current_user
from app.users.models import User

from . import service
from .schemas import ChallengeDetail, ChallengeSummary

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("", response_model=list[ChallengeSummary])
def list_challenges(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.list_path(db, user)


@router.get("/{slug}", response_model=ChallengeDetail)
def get_challenge(
    slug: str,
    include_solution: bool = Query(False, description="Return the reference solution (only after a submission)"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return service.detail(db, user, slug, include_solution)


@router.get("/{slug}/submissions", response_model=list[SubmissionOut])
def list_submissions(slug: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return submission_service.history(db, user, service.get_by_slug(db, slug))
