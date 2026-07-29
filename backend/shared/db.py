from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.config import get_database_url


class Base(DeclarativeBase):
    pass


def create_db_engine():
    db_url = get_database_url()
    kwargs: dict = {"future": True}

    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL — connection pool tuning
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10

    engine = create_engine(db_url, **kwargs)

    # Enable WAL mode for SQLite (better concurrency)
    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return engine


ENGINE = create_db_engine()
SessionLocal = sessionmaker(bind=ENGINE, autocommit=False, autoflush=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from shared import models  # noqa: F401 — registers ORM classes
    try:
        Base.metadata.create_all(bind=ENGINE)
    except Exception as e:
        import logging
        logging.warning(f"Database initialization skipped or failed: {e}")
