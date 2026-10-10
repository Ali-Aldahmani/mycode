"""Who is making the request.

v1 has no authentication: everything belongs to the single seeded user. A
future `auth` module replaces this dependency; routes don't change.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_db

from .models import User
from .service import get_or_create_default_user


def current_user(db: Session = Depends(get_db)) -> User:
    return get_or_create_default_user(db)
