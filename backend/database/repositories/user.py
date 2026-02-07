from datetime import UTC, datetime
from typing import cast

from cashews import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, select, update

from backend.database.tables import User
from backend.utils.encryption import EncryptionService


class UserRepository:
    @staticmethod
    @cache(ttl="15m", key="user:login:{login}")
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
    @cache(ttl="15m", key="user:email:{email}")
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

    @staticmethod
    @cache.invalidate(key_template="user:login:{login}")
    @cache.invalidate(key_template="user:email:{email}")
    async def create_user(session: AsyncSession, login: str, email: str, password: str) -> None:
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

    @staticmethod
    @cache.invalidate(key_template="user:login:{login}")
    @cache.invalidate(key_template="user:email:{email}")
    async def change_user_password(session: AsyncSession, login: str, new_password: str) -> int:
        """
        Change the password of a user.

        Args:
            session (AsyncSession): The current session.
            user_id (int): The ID of the user.
            new_password (str): The new password of the user.

        Returns:
            int: The number of rows updated.
        """
        hash_ = EncryptionService.hash_password(new_password)
        stmt = (
            update(User)
            .where(cast(Column, User.login == login))
            .values(password=hash_, password_change_date=datetime.now(UTC))
        )
        result = await session.execute(stmt)
        return result.rowcount if hasattr(result, "rowcount") else 0

    @staticmethod
    @cache.invalidate(key_template="user:login:{login}")
    async def update_avatar_url(session: AsyncSession, login: str, avatar_name: str) -> int:
        """
        Update the avatar URL of a user.

        Args:
            session (AsyncSession): The current session.
            login (str): The login of the user.
            avatar_name (str): The new avatar name in MinIO.

        Returns:
            int: The number of rows updated.
        """
        stmt = update(User).where(cast(Column, User.login == login)).values(avatar_name=avatar_name)
        result = await session.execute(stmt)
        return result.rowcount if hasattr(result, "rowcount") else 0
