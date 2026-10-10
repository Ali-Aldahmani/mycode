from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))  # correct | wrong | error
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # which help had been opened when this was submitted
    hints_used: Mapped[list[str]] = mapped_column(JSON, default=list)
    used_example: Mapped[bool] = mapped_column(Boolean, default=False)
    used_hint_1: Mapped[bool] = mapped_column(Boolean, default=False)
    used_hint_2: Mapped[bool] = mapped_column(Boolean, default=False)
    # counted attempts (correct + wrong) in this round, including this one; null for errors
    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    round: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
