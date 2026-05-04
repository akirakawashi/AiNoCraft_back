from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from cashews import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, select, update

from backend.database.tables import User
from backend.redis.cache.keyspace import CacheKeyspace
from backend.utils.encryption import EncryptionService

USER_CACHE = CacheKeyspace.from_file(__file__)
USER_BY_LOGIN_TEMPLATE = "login:{login}"
USER_BY_EMAIL_TEMPLATE = "email:{email}"


class UserRepository:
    @classmethod
    def _login_cache_key(cls, login: str) -> str:
        return USER_CACHE.key(USER_BY_LOGIN_TEMPLATE, login=login)

    @classmethod
    def _email_cache_key(cls, email: str) -> str:
        return USER_CACHE.key(USER_BY_EMAIL_TEMPLATE, email=email)

    @classmethod
    async def _invalidate_lookup_cache(
        cls,
        *,
        login: str | None = None,
        email: str | None = None,
    ) -> None:
        keys: set[str] = set()

        if login is not None:
            keys.add(cls._login_cache_key(login))
        if email is not None:
            keys.add(cls._email_cache_key(email))

        if keys:
            await cache.delete_many(*keys)

    @staticmethod
    async def _get_user_email_by_login(session: AsyncSession, login: str) -> str | None:
        stmt = select(User.email).where(User.login == login)
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        """
        Select a user by ID.

        Args:
            session (AsyncSession): The current session.
            user_id (UUID): The ID of the user to select.

        Returns:
            User | None: The user if found, None otherwise.
        """
        stmt = select(User).where(User.user_id == user_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    @USER_CACHE.cached(ttl="15m", template=USER_BY_LOGIN_TEMPLATE)
    async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
        """
        Select a user by login.

        Args:
            session (AsyncSession): The current session.
            login (str): The login of the user to select.

        Returns:
            int | None: The id of the user if found, None otherwise.
        """
        stmt = select(User).where(User.login == login)
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    @USER_CACHE.cached(ttl="15m", template=USER_BY_EMAIL_TEMPLATE)
    async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
        """
        Select a user by email.

        Args:
            session (AsyncSession): The current session.
            email (str): The email of the user to select.

        Returns:
            int | None: The id of the user if found, None otherwise.
        """
        stmt = select(User).where(User.email == email)
        return (await session.execute(stmt)).scalar_one_or_none()

    @classmethod
    @USER_CACHE.invalidate(USER_BY_LOGIN_TEMPLATE)
    @USER_CACHE.invalidate(USER_BY_EMAIL_TEMPLATE)
    async def create_user(
        cls, session: AsyncSession, login: str, email: str, password: str
    ) -> None:
        """
        Create a new user and invalidate related caches.

        Args:
            session (AsyncSession): The current session.
            login (str): The login of the user to create.
            email (str): The email of the user to create.
            password (str): The password of the user to create.

        Returns:
            None
        """
        user = User(login=login, email=email, password=password)
        session.add(user)

    @classmethod
    async def change_user_password(
        cls, session: AsyncSession, login: str, new_password: str
    ) -> int:
        """
        Change the password of a user.

        Args:
            session (AsyncSession): The current session.
            user_id (int): The ID of the user.
            new_password (str): The new password of the user.

        Returns:
            int: The number of rows updated.
        """
        email = await cls._get_user_email_by_login(session, login)
        if email is None:
            return 0

        hash_ = EncryptionService.hash_password(new_password)
        stmt = (
            update(User)
            .where(cast(Column, User.login == login))
            .values(password=hash_, password_change_date=datetime.now(UTC))
        )
        result = await session.execute(stmt)
        await cls._invalidate_lookup_cache(login=login, email=email)
        return result.rowcount if hasattr(result, "rowcount") else 0

    @classmethod
    async def update_avatar_url(cls, session: AsyncSession, login: str, avatar_name: str) -> int:
        """
        Update the avatar URL of a user.

        Args:
            session (AsyncSession): The current session.
            login (str): The login of the user.
            avatar_name (str): The new avatar name in MinIO.

        Returns:
            int: The number of rows updated.
        """
        email = await cls._get_user_email_by_login(session, login)
        if email is None:
            return 0

        stmt = update(User).where(cast(Column, User.login == login)).values(avatar_name=avatar_name)
        result = await session.execute(stmt)
        await cls._invalidate_lookup_cache(login=login, email=email)
        return result.rowcount if hasattr(result, "rowcount") else 0
