import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.challenges.schemas import ChallengeSeed
from app.challenges.service import upsert
from app.core import models  # noqa: F401
from app.core.db import Base, get_db
from app.main import app

PEOPLE = {
    "type": "dataframe",
    "columns": ["name", "age"],
    "data": [["Ana", 34], ["Ben", 28], ["Cleo", 45]],
}

BASE_SEED = {
    "slug": "filter-age",
    "order": 1,
    "level": 2,
    "title": "Older than 30",
    "method": "boolean filter",
    "category": "Pick",
    "task": "Keep the people older than 30.",
    "inputs": {"df": PEOPLE},
    "target": {"type": "dataframe", "columns": ["name", "age"], "data": [["Ana", 34], ["Cleo", 45]], "index": [0, 2]},
    "hint_1": "Keep only some rows based on a condition.",
    "hint_2": "df[df[___] ___ ___]",
    "example": {
        "inputs": {"cars": {"type": "dataframe", "columns": ["model", "hp"], "data": [["a", 90], ["b", 200]]}},
        "code": "result = cars[cars['hp'] > 100]",
    },
    "reference_solution": "result = df[df['age'] > 30]",
    "docs_url": "https://pandas.pydata.org/docs/user_guide/indexing.html#boolean-indexing",
    "visual_type": "fade_out",
}


def seed(**overrides) -> dict:
    s = copy.deepcopy(BASE_SEED)
    s.update(overrides)
    return s


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    with session_factory() as db:
        upsert(db, [
            ChallengeSeed.model_validate(seed()),
            ChallengeSeed.model_validate(seed(slug="sort-age", order=2, title="Sort by age",
                                              reference_solution="result = df.sort_values('age')")),
        ])

    def override():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
