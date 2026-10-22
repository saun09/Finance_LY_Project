import os

import pytest
from sqlalchemy.orm import Session

from app.crypto import generate_key

# Encrypted columns need a key; a throwaway per-run one keeps the suite
# independent of whatever is (or isn't) in backend/.env.
os.environ["DATA_ENCRYPTION_KEY"] = generate_key()

import app.models  # noqa: F401 — registers models on Base.metadata
from app.db import Base, make_engine


@pytest.fixture()
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()
