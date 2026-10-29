from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal = None


def get_engine_url(testing: bool = False) -> str:
    import os

    settings = get_settings()
    if testing:
        return os.getenv("TEST_DATABASE_URL", settings.test_database_url)
    return settings.database_url


def init_engine(testing: bool = False):
    global _engine, _SessionLocal
    url = get_engine_url(testing)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_engine():
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    print(factory)
    db = factory()
    print(db)
    try:
        yield db
    finally:
        db.close()

