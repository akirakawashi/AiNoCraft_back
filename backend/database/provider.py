from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import text

from backend.api.exceptions.base import ApiBaseException
from backend.config import db_settings


class DatabaseProvider:
    _engine: AsyncEngine | None = None
    _session_maker: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    async def init_engine(cls) -> None:
        """
        Initialize the database engine.

        If the engine is not initialized, create a new one with the pool size and max overflow from the database settings.
        """
        if cls._engine is None:
            logger.debug(
                f"Creating database engine: pool_size={db_settings.pool_size}, "
                f"max_overflow={db_settings.max_overflow}"
            )
            cls._engine = create_async_engine(
                db_settings.async_url,
                pool_size=db_settings.pool_size,
                max_overflow=db_settings.max_overflow,
            )
            cls._session_maker = async_sessionmaker(
                cls._engine, expire_on_commit=False, class_=AsyncSession
            )
        try:
            async with cls.session_lifecycle() as session:
                await session.execute(text("SELECT 1"))
            logger.debug("Database connection established")
        except Exception:
            logger.error("Database connection error")
            raise

    @classmethod
    async def dispose_engine(cls) -> None:
        """
        Dispose the database engine.

        If the engine is not None, dispose it and log a message.
        Set the engine and session maker to None.
        """
        if cls._engine is not None:
            await cls._engine.dispose()
            logger.debug("Database engine disposed")
            cls._engine = None
            cls._session_maker = None

    @classmethod
    @asynccontextmanager
    async def session_lifecycle(cls) -> AsyncIterator[AsyncSession]:
        """
        A context manager that yields an AsyncSession object.

        This context manager is used to ensure that a database session is
        properly closed after use. It also logs a message when the session
        is created and closed.

        It raises a RuntimeError if the engine is not initialized.

        Usage:

            async with cls.session_lifecycle() as session:
                # Do something with the session
        """
        if cls._session_maker is None:
            raise RuntimeError("Engine is not initialized. Call init_engine() at app startup.")
        logger.debug("Creating new database session")
        async with cls._session_maker() as session:
            try:
                yield session
                await session.commit()
            except ApiBaseException as e:
                await session.rollback()
                logger.debug(f"Session rollback due to ApiBaseException: {repr(e)}")
                raise
            except Exception:
                await session.rollback()
                logger.exception("Session rollback due to unexpected exception")
                raise
            finally:
                logger.debug("Database session closed")

    @classmethod
    async def get_session(cls):
        """
        Get a database session.

        This method is a shortcut for using the session lifecycle context manager.
        It yields a single AsyncSession object that is properly closed after use.

        Usage:

            async for session in cls.get_session():
                # Do something with the session
        """
        async with cls.session_lifecycle() as session:
            yield session
