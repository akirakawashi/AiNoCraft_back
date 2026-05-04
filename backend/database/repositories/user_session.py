from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, and_, func, not_, select, update

from backend.database.tables import UserSession
from backend.utils.encryption import EncryptionService


class UserSessionRepository:
    @staticmethod
    async def update_refresh_token(
        session: AsyncSession,
        session_id: int,
        new_refresh_token: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> None:
        """
        Update the refresh token for the given session.

        Args:
            session (AsyncSession): The current database session.
            session_id (int): The session ID to update.
            new_refresh_token (str): The new refresh token to store.
            expires_at (datetime): The new token expiration datetime.
            user_agent (str | None): The user agent string.
            ip_address (str | None): The IP address.

        Returns:
            None
        """
        new_token_hash = EncryptionService.sha256(new_refresh_token)

        stmt = (
            update(UserSession)
            .where(
                and_(
                    cast(Column, UserSession.session_id == session_id),
                    cast(Column, UserSession.user_agent == user_agent),
                    cast(Column, UserSession.ip_address == ip_address),
                )
            )
            .values(
                refresh_token_hash=new_token_hash,
                last_used_at=func.now(),
                expires_at=expires_at,
            )
        )
        await session.execute(stmt)

    @staticmethod
    async def find_valid_session_by_token(
        session: AsyncSession,
        user_id: UUID,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession | None:
        """
        Find a valid user session by a refresh token.

        Args:
            session: The current database session.
            user_id: The user ID.
            refresh_token: The refresh token to verify.
            user_agent: The user agent string (optional).
            ip_address: The IP address (optional).

        Returns:
            A valid user session if the token is valid, otherwise None.
        """
        token_hash = EncryptionService.sha256(refresh_token)

        conditions: list[Column] = [
            cast(Column, UserSession.user_id == user_id),
            cast(Column, not_(UserSession.revoked)),
            cast(Column, UserSession.expires_at > func.now()),
            cast(Column, UserSession.refresh_token_hash == token_hash),
        ]

        if user_agent is not None:
            conditions.append(cast(Column, UserSession.user_agent == user_agent))
        if ip_address is not None:
            conditions.append(cast(Column, UserSession.ip_address == ip_address))

        stmt = select(UserSession).where(and_(*conditions))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_session(
        session: AsyncSession,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        """
        Create a new user session.

        Args:
            session: The current session.
            user_id: The user ID.
            refresh_token_hash: The hashed refresh token.
            expires_at: The token expiration datetime.
            user_agent: The user agent string.
            ip_address: The IP address.

        Returns:
            The created user session.
        """
        user_session = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            revoked=False,
            created_at=func.now(),
            last_used_at=func.now(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(user_session)
        return user_session

    @staticmethod
    async def get_by_refresh_token_hash(
        session: AsyncSession, refresh_token_hash: str
    ) -> UserSession | None:
        """
        Retrieve a UserSession object from the database by its refresh token hash.

        Args:
            session (AsyncSession): The current database session.
            refresh_token_hash (str): The hash of the refresh token.

        Returns:
            UserSession | None: The UserSession object if found, None otherwise.
        """
        stmt = select(UserSession).where(UserSession.refresh_token_hash == refresh_token_hash)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_session(session: AsyncSession, session_id: int) -> None:
        """
        Mark a session as revoked in the database.

        Args:
            session (AsyncSession): The current database session.
            session_id (int): The ID of the session to revoke.

        Returns:
            None
        """
        stmt = (
            update(UserSession)
            .where(cast(Column, UserSession.session_id == session_id))
            .values(revoked=True)
        )
        await session.execute(stmt)

    @staticmethod
    async def update_last_used_at(session: AsyncSession, session_id: int) -> None:
        """
        Update the last used at timestamp for a given session ID.

        Args:
            session (AsyncSession): The current session.
            session_id (int): The session ID to update.

        Returns:
            None
        """
        stmt = (
            update(UserSession)
            .where(cast(Column, UserSession.session_id == session_id))
            .values(last_used_at=func.now())
        )
        await session.execute(stmt)

    @staticmethod
    async def revoke_current_sessions(
        session: AsyncSession, user_id: UUID, user_agent: str | None, ip_address: str | None
    ) -> int:
        """
        Revoke all current sessions for a user that match the given user agent and IP address.

        Args:
            session (AsyncSession): The current session.
            user_id (int): The ID of the user.
            user_agent (str | None): The user agent string to match.
            ip_address (str | None): The IP address to match.

        Returns:
            int: The number of sessions revoked.
        """
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    not_(UserSession.revoked),
                    UserSession.user_agent == user_agent,
                    UserSession.ip_address == ip_address,
                )
            )
            .values(revoked=True)
        )
        result = await session.execute(stmt)
        return result.rowcount if hasattr(result, "rowcount") else 0

    @staticmethod
    async def revoke_all_sessions(session: AsyncSession, user_id: UUID) -> int:
        """
        Revoke all sessions for a user.

        Args:
            session (AsyncSession): The current session.
            user_id (int): The ID of the user.

        Returns:
            int: The number of sessions revoked.
        """
        stmt = (
            update(UserSession)
            .where(
                and_(
                    cast(Column, UserSession.user_id == user_id),
                    not_(UserSession.revoked),
                )
            )
            .values(revoked=True)
        )
        result = await session.execute(stmt)
        return result.rowcount if hasattr(result, "rowcount") else 0
