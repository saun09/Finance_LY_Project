import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — registers models on Base.metadata
from app.db import Base, make_engine


@pytest.fixture()
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()
