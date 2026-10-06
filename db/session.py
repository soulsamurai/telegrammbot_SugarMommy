"""Асинхронная сессия SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(db_url: str, echo: bool = False) -> async_sessionmaker[AsyncSession]:
    """Инициализирует engine и фабрику сессий (вызывается один раз при старте)."""
    global _engine, _session_factory
    _engine = create_async_engine(db_url, echo=echo, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("БД не инициализирована: вызовите init_db()")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-style генератор сессии."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_db() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
