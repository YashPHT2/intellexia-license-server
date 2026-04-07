"""Database engine, session factory, and declarative base."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Render provides postgres:// but SQLAlchemy 2.x needs postgresql://
_url = settings.DATABASE_URL
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    _url,
    pool_pre_ping=True,
    echo=(not settings.is_production),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency – yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
