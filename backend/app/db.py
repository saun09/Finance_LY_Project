from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def enum_values(enum_cls) -> list[str]:
    """`values_callable` for every sa.Enum column: store each member's
    lowercase *value* ("regular"), which is what the migrations created the
    Postgres enum types with -- SQLAlchemy's default is the member *name*
    ("REGULAR"), which SQLite silently accepted but Postgres rejects."""
    return [member.value for member in enum_cls]


def make_engine(database_url: str = DATABASE_URL):
    if not database_url.startswith("sqlite"):
        return create_engine(database_url, pool_pre_ping=True)

    connect_args = {"check_same_thread": False}
    if ":memory:" in database_url:
        # A plain in-memory SQLite engine hands each new connection a
        # separate, empty database — fine for a single-threaded test, but
        # FastAPI's TestClient dispatches requests via a worker threadpool,
        # so a multi-request test can silently get a fresh empty DB
        # mid-flow ("no such table") once a request lands on a different
        # thread. StaticPool pins the whole engine to one shared connection
        # so every thread sees the same in-memory database.
        return create_engine(database_url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(database_url, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
