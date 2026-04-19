from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # pyright: ignore[reportMissingImports]

from app.settings import DB_URL

_default_url = f"sqlite:///{Path(__file__).parent.parent / 'garage.db'}"
SQLALCHEMY_DATABASE_URL = DB_URL or _default_url

_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Postgres-only pool tuning. Neon (and similar serverless Postgres) auto-suspend
# idle compute and may close pooled connections behind our back; pool_pre_ping
# revalidates each checkout, and pool_recycle proactively rotates connections
# before they age into Neon's idle-timeout window. pool_size + max_overflow are
# kept small to stay well under Neon free-tier connection caps.
_engine_kwargs: dict = {"connect_args": _connect_args}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
