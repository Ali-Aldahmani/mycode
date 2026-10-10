from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.progress.schemas import ChallengeProgressOut, OverallProgress


class SubmissionIn(BaseModel):
    """Facts about a submission. The browser ran and checked the code; the
    server only records the facts and computes the score."""

    challenge_slug: str
    code: str = Field(max_length=20_000)
    status: Literal["correct", "wrong", "error"]
    used_example: bool = False
    used_hint_1: bool = False
    used_hint_2: bool = False
    error: str | None = Field(default=None, max_length=2_000)
    reason: str | None = Field(default=None, max_length=500)
    runtime_ms: float | None = None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    code: str
    status: str
    score: int | None
    hints_used: list[str]
    used_example: bool
    used_hint_1: bool
    used_hint_2: bool
    attempt_number: int | None
    round: int
    error: str | None
    reason: str | None
    runtime_ms: float | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        # SQLite drops the timezone; every timestamp is stored in UTC
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


class SubmissionResult(BaseModel):
    submission: SubmissionOut
    progress: ChallengeProgressOut
    overall: OverallProgress
    # what a correct answer would score now (after this submission)
    potential: int
    next_slug: str | None
    unlocked_next: bool
