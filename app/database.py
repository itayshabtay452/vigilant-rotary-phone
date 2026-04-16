from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # pyright: ignore[reportMissingImports]

from app.settings import DB_URL

_default_url = f"sqlite:///{Path(__file__).parent.parent / 'garage.db'}"
SQLALCHEMY_DATABASE_URL = DB_URL or _default_url

_connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
