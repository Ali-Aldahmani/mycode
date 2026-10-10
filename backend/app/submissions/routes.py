from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.users.deps import current_user
from app.users.models import User

from . import service
from .schemas import SubmissionIn, SubmissionResult

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResult, status_code=201)
def create_submission(data: SubmissionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return service.create(db, user, data)
