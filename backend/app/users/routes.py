from fastapi import APIRouter, Depends

from .deps import current_user
from .models import User
from .schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user
