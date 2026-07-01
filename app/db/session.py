"""
Database engine and session management.

This module is the single source of truth for how the app connects to
the database. Services/APIs never construct engines or sessions
themselves — they always go through `get_db()`.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models. Every model inherits from this."""

    pass


# `connect_args` is SQLite-specific: by default SQLite only allows the
# thread that created a connection to use it, which breaks under
# FastAPI's threaded request handling. This flag disables that check.
# When we migrate to PostgreSQL later, this arg is simply dropped.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=False,  # set True temporarily if you need to debug raw SQL
)

# Each call to SessionLocal() creates a new session. We don't share
# sessions across requests — that's what causes hard-to-debug
# concurrency bugs in production.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees
    it's closed afterward, even if an exception occurs mid-request.

    Usage in a route:
        def endpoint(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        logger.exception("Database session error — rolling back.")
        db.rollback()
        raise
    finally:
        db.close()