from collections.abc import Generator

from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # pyright: ignore[reportMissingImports]

SQLALCHEMY_DATABASE_URL = "sqlite:///./garage.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
