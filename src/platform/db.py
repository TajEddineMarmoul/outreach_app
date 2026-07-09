from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{(PROJECT_ROOT / 'data' / 'outreach_app.db').as_posix()}"


class Base(DeclarativeBase):
    pass


def _normalize_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw_url


def get_database_url() -> str:
    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").lower()
    raw_url = os.getenv("APP_DATABASE_URL")
    if raw_url:
        return _normalize_database_url(raw_url)

    if env in {"production", "prod"}:
        raw_url = os.getenv("DATABASE_URL")
        if raw_url:
            return _normalize_database_url(raw_url)
        raise RuntimeError("APP_DATABASE_URL or DATABASE_URL is required in production.")

    return DEFAULT_SQLITE_URL


def get_engine() -> Engine:
    url = get_database_url()
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite:"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, future=True, **kwargs)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
