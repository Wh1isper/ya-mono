from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def _is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def create_engine(database_url: str, **kwargs: object) -> AsyncEngine:
    defaults: dict[str, object] = {
        "echo": False,
        "pool_pre_ping": True,
    }

    if _is_sqlite_url(database_url):
        defaults["connect_args"] = {"check_same_thread": False}
    else:
        defaults.update({
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 3600,
        })

    if "connect_args" in kwargs and "connect_args" in defaults:
        merged_connect_args = dict(defaults["connect_args"])
        merged_connect_args.update(kwargs.pop("connect_args"))
        defaults["connect_args"] = merged_connect_args

    defaults.update(kwargs)
    return create_async_engine(database_url, **defaults)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def to_sync_database_url(database_url: str) -> str:
    return (
        database_url
        .replace("sqlite+aiosqlite://", "sqlite://")
        .replace("postgresql+asyncpg://", "postgresql+psycopg://")
        .replace("postgresql+psycopg_async://", "postgresql+psycopg://")
    )
