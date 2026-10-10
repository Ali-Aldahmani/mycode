from pydantic import BaseModel, ConfigDict


class ChallengeProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    challenge_id: int
    best_score: int | None
    solved: bool
    unlocked: bool
    help_used: list[str]


class CategoryProgress(BaseModel):
    level: int
    category: str
    solved: int
    total: int
    average: float | None


class OverallProgress(BaseModel):
    solved: int
    total: int
    total_score: int
    average: float | None


class ProgressOut(BaseModel):
    overall: OverallProgress
    categories: list[CategoryProgress]


class HelpIn(BaseModel):
    kind: str


class HelpOut(BaseModel):
    help_used: list[str]
    cost: int
