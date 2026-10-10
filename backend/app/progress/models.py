from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", name="uq_progress_user_challenge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), index=True)
    best_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    # help opened in the current round (a round ends with a correct submission)
    help_used: Mapped[list[str]] = mapped_column(JSON, default=list)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
