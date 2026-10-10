"""Challenge schemas: the seed-file format (ChallengeSeed) and API responses."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

VISUAL_TYPES = ("show", "fade_out", "slide", "appear", "scan", "cluster", "collapse", "connect", "move_cells")
CHECKER_OPTIONS = {"check_row_order", "check_column_order", "check_index", "check_dtype", "check_names", "rtol"}


class ValueSpec(BaseModel):
    """A DataFrame, Series or scalar in JSON form (see /pyengine/valuespec.py)."""

    model_config = ConfigDict(extra="allow")

    type: Literal["dataframe", "series", "scalar"]

    @model_validator(mode="after")
    def _shape(self) -> "ValueSpec":
        data = self.model_extra or {}
        if self.type == "dataframe":
            cols, rows = data.get("columns"), data.get("data")
            if not isinstance(cols, list) or not isinstance(rows, list):
                raise ValueError("a dataframe needs 'columns' and 'data' lists")
            for row in rows:
                if not isinstance(row, list) or len(row) != len(cols):
                    raise ValueError(f"every row must have {len(cols)} values: {row!r}")
            if "index" in data and len(data["index"]) != len(rows):
                raise ValueError("'index' must have one label per row")
        elif self.type == "series":
            if not isinstance(data.get("data"), list):
                raise ValueError("a series needs a 'data' list")
            if "index" in data and len(data["index"]) != len(data["data"]):
                raise ValueError("'index' must have one label per value")
        elif "value" not in data:
            raise ValueError("a scalar needs a 'value'")
        return self


class Example(BaseModel):
    """The same method on different data, animated by the same engine."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, ValueSpec]
    code: str
    note: str = ""


class ChallengeSeed(BaseModel):
    """One file in /challenges. Validated before it can reach the database."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    order: int = Field(ge=1)
    level: int = Field(ge=1)
    title: str
    method: str
    category: str
    language: Literal["python"] = "python"
    library: Literal["pandas"] = "pandas"
    source: Literal["official", "community", "ai_generated"] = "official"
    task: str
    inputs: dict[str, ValueSpec]
    target: ValueSpec
    starter_code: str = "result = "
    hint_1: str
    hint_2: str
    example: Example
    reference_solution: str
    why: str = ""
    docs_url: HttpUrl
    checker_type: Literal["pandas_equal"] = "pandas_equal"
    checker_options: dict[str, Any] = Field(default_factory=dict)
    visual_type: str = "appear"

    @field_validator("visual_type")
    @classmethod
    def _visual(cls, v: str) -> str:
        if v not in VISUAL_TYPES:
            raise ValueError(f"visual_type must be one of {VISUAL_TYPES}")
        return v

    @field_validator("checker_options")
    @classmethod
    def _options(cls, v: dict[str, Any]) -> dict[str, Any]:
        unknown = set(v) - CHECKER_OPTIONS
        if unknown:
            raise ValueError(f"unknown checker options: {sorted(unknown)}")
        return v

    @field_validator("inputs")
    @classmethod
    def _names(cls, v: dict[str, ValueSpec]) -> dict[str, ValueSpec]:
        if not v:
            raise ValueError("a challenge needs at least one input")
        for name in v:
            if not name.isidentifier():
                raise ValueError(f"input name {name!r} is not a valid Python identifier")
        return v

    def db_fields(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["docs_url"] = str(self.docs_url)
        return data


class Costs(BaseModel):
    example: int
    hint_1: int
    hint_2: int


class DisplayTables(BaseModel):
    """Tables pre-rendered by the engine with real pandas, so the page can
    show them before Pyodide has loaded (frame-contract TableState dicts)."""

    inputs: list[dict[str, Any]]
    target: dict[str, Any]
    example_inputs: list[dict[str, Any]]


class ChallengeSummary(BaseModel):
    """One entry of the path."""

    id: int
    slug: str
    order: int
    level: int
    title: str
    method: str
    category: str
    locked: bool
    solved: bool
    best_score: int | None


class ChallengeDetail(BaseModel):
    id: int
    slug: str
    order: int
    level: int
    title: str
    method: str
    category: str
    language: str
    library: str
    source: str
    task: str
    inputs: dict[str, Any]
    target: dict[str, Any]
    starter_code: str
    hint_1: str
    hint_2: str
    example: dict[str, Any]
    why: str
    docs_url: str
    checker_type: str
    checker_options: dict[str, Any]
    visual_type: str
    costs: Costs
    locked: bool
    solved: bool
    best_score: int | None
    submitted: bool
    prev_slug: str | None
    next_slug: str | None
    total: int
    # help opened in the current round, and what a correct answer would score now
    help_used: list[str]
    potential: int
    display: DisplayTables
    # only returned after the user has submitted at least once, and only when asked for
    reference_solution: str | None = None
