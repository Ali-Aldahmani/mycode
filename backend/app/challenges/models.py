from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, JSONType, TimestampMixin, utcnow


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    order: Mapped[int] = mapped_column("order", Integer, unique=True, index=True)
    level: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    method: Mapped[str] = mapped_column(String(96))
    category: Mapped[str] = mapped_column(String(64))

    language: Mapped[str] = mapped_column(String(32), default="python")
    library: Mapped[str] = mapped_column(String(32), default="pandas")
    source: Mapped[str] = mapped_column(String(32), default="official")

    task: Mapped[str] = mapped_column(Text)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONType)
    target: Mapped[dict[str, Any]] = mapped_column(JSONType)
    starter_code: Mapped[str] = mapped_column(Text, default="result = ")
    hint_1: Mapped[str] = mapped_column(Text)
    hint_2: Mapped[str] = mapped_column(Text)
    example: Mapped[dict[str, Any]] = mapped_column(JSONType)
    reference_solution: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text, default="")
    docs_url: Mapped[str] = mapped_column(String(300))

    checker_type: Mapped[str] = mapped_column(String(48), default="pandas_equal")
    checker_options: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    visual_type: Mapped[str] = mapped_column(String(48), default="appear")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
