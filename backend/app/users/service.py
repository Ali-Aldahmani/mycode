from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings

from .models import User


def get_or_create_default_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.username == settings.default_username))
    if user is None:
        user = User(username=settings.default_username, display_name="Me")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
