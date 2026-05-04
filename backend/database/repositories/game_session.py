import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from cashews import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, and_, desc, func, not_, or_, select, update

from backend.database.tables import GameSession, User
from backend.redis.cache.keyspace import CacheKeyspace
from backend.utils.encryption import EncryptionService

GAME_SESSION_CACHE = CacheKeyspace.from_file(__file__)
GAME_SESSION_ACCESS_CACHE = GAME_SESSION_CACHE.scope("access")
GAME_SESSION_REFRESH_CACHE = GAME_SESSION_CACHE.scope("refresh")
GAME_SESSION_ACCESS_LOOKUP_TEMPLATE = "{access_token_hash}:{client_token_key}"
GAME_SESSION_REFRESH_LOOKUP_TEMPLATE = "{refresh_token_hash}:{client_token_key}"


class GameSessionRepository:
    _NO_CLIENT_TOKEN = "__none__"

    @staticmethod
    def _token_hash(token: str) -> str:
        return EncryptionService.sha256(token)

    @classmethod
    def _normalize_client_token(cls, client_token: str | None) -> str:
        return client_token if client_token is not None else cls._NO_CLIENT_TOKEN

    @classmethod
    def _client_token_from_key(cls, client_token_key: str) -> str | None:
        return None if client_token_key == cls._NO_CLIENT_TOKEN else client_token_key

    @classmethod
    def _access_cache_key(cls, access_token_hash: str, client_token: str | None) -> str:
        return GAME_SESSION_ACCESS_CACHE.key(
            GAME_SESSION_ACCESS_LOOKUP_TEMPLATE,
            access_token_hash=access_token_hash,
            client_token_key=cls._normalize_client_token(client_token),
        )

    @classmethod
    def _refresh_cache_key(cls, refresh_token_hash: str, client_token: str | None) -> str:
        return GAME_SESSION_REFRESH_CACHE.key(
            GAME_SESSION_REFRESH_LOOKUP_TEMPLATE,
            refresh_token_hash=refresh_token_hash,
            client_token_key=cls._normalize_client_token(client_token),
        )

    @classmethod
    async def _invalidate_lookup_cache(
        cls,
        access_token_hash: str | None = None,
        refresh_token_hash: str | None = None,
        client_token: str | None = None,
    ) -> None:
        keys: set[str] = set()

        if access_token_hash is not None:
            keys.add(cls._access_cache_key(access_token_hash, None))
            keys.add(cls._access_cache_key(access_token_hash, client_token))

        if refresh_token_hash is not None:
            keys.add(cls._refresh_cache_key(refresh_token_hash, None))
            keys.add(cls._refresh_cache_key(refresh_token_hash, client_token))

        if keys:
            await cache.delete_many(*keys)

    @staticmethod
    @GAME_SESSION_ACCESS_CACHE.cached(ttl="5m", template=GAME_SESSION_ACCESS_LOOKUP_TEMPLATE)
    async def _get_valid_by_access_token_hash_cached(
        session: AsyncSession,
        access_token_hash: str,
        client_token_key: str,
    ) -> GameSession | None:
        client_token = GameSessionRepository._client_token_from_key(client_token_key)

        conditions: list[Column] = [
            cast(Column, GameSession.access_token_hash == access_token_hash),
            cast(Column, not_(GameSession.revoked)),
            cast(Column, GameSession.access_expires_at > func.now()),
        ]
        if client_token is not None:
            conditions.append(cast(Column, GameSession.client_token == client_token))

        stmt = select(GameSession).where(and_(*conditions))
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    @GAME_SESSION_REFRESH_CACHE.cached(ttl="5m", template=GAME_SESSION_REFRESH_LOOKUP_TEMPLATE)
    async def _get_valid_by_refresh_token_hash_cached(
        session: AsyncSession,
        refresh_token_hash: str,
        client_token_key: str,
    ) -> GameSession | None:
        client_token = GameSessionRepository._client_token_from_key(client_token_key)

        conditions: list[Column] = [
            cast(Column, GameSession.refresh_token_hash == refresh_token_hash),
            cast(Column, not_(GameSession.revoked)),
            cast(Column, GameSession.refresh_expires_at > func.now()),
        ]
        if client_token is not None:
            conditions.append(cast(Column, GameSession.client_token == client_token))

        stmt = select(GameSession).where(and_(*conditions))
        return (await session.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def create_session(
        cls,
        session: AsyncSession,
        user_id: UUID,
        client_token: str,
        access_token: str,
        refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> GameSession:
        access_token_hash = cls._token_hash(access_token)
        refresh_token_hash = cls._token_hash(refresh_token)
        game_session = GameSession(
            user_id=user_id,
            client_token=client_token,
            access_token_hash=access_token_hash,
            refresh_token_hash=refresh_token_hash,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            revoked=False,
            last_used_at=datetime.now(tz=UTC),
        )
        session.add(game_session)

        await cls._invalidate_lookup_cache(
            access_token_hash=access_token_hash,
            refresh_token_hash=refresh_token_hash,
            client_token=client_token,
        )

        return game_session

    @classmethod
    async def get_valid_by_access_token(
        cls,
        session: AsyncSession,
        access_token: str,
        client_token: str | None = None,
    ) -> GameSession | None:
        access_token_hash = cls._token_hash(access_token)
        return await cls._get_valid_by_access_token_hash_cached(
            session=session,
            access_token_hash=access_token_hash,
            client_token_key=cls._normalize_client_token(client_token),
        )

    @classmethod
    async def get_valid_by_refresh_token(
        cls,
        session: AsyncSession,
        refresh_token: str,
        client_token: str | None = None,
    ) -> GameSession | None:
        refresh_token_hash = cls._token_hash(refresh_token)
        return await cls._get_valid_by_refresh_token_hash_cached(
            session=session,
            refresh_token_hash=refresh_token_hash,
            client_token_key=cls._normalize_client_token(client_token),
        )

    @classmethod
    async def rotate_tokens(
        cls,
        session: AsyncSession,
        session_id: int,
        new_access_token: str,
        new_refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        current_stmt = select(GameSession).where(
            and_(
                cast(Column, GameSession.session_id == session_id),
                cast(Column, not_(GameSession.revoked)),
            )
        )
        current_session = (await session.execute(current_stmt)).scalar_one_or_none()
        if not current_session:
            return

        new_access_token_hash = cls._token_hash(new_access_token)
        new_refresh_token_hash = cls._token_hash(new_refresh_token)

        stmt = (
            update(GameSession)
            .where(
                and_(
                    cast(Column, GameSession.session_id == session_id),
                    cast(Column, not_(GameSession.revoked)),
                )
            )
            .values(
                access_token_hash=new_access_token_hash,
                refresh_token_hash=new_refresh_token_hash,
                access_expires_at=access_expires_at,
                refresh_expires_at=refresh_expires_at,
                last_used_at=func.now(),
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        await session.execute(stmt)

        await asyncio.gather(
            cls._invalidate_lookup_cache(
                access_token_hash=current_session.access_token_hash,
                refresh_token_hash=current_session.refresh_token_hash,
                client_token=current_session.client_token,
            ),
            cls._invalidate_lookup_cache(
                access_token_hash=new_access_token_hash,
                refresh_token_hash=new_refresh_token_hash,
                client_token=current_session.client_token,
            ),
        )

    @staticmethod
    async def revoke_session(session: AsyncSession, session_id: int) -> None:
        session_stmt = select(GameSession).where(cast(Column, GameSession.session_id == session_id))
        game_session = (await session.execute(session_stmt)).scalar_one_or_none()
        if not game_session:
            return

        stmt = (
            update(GameSession)
            .where(cast(Column, GameSession.session_id == session_id))
            .values(revoked=True)
        )
        await session.execute(stmt)

        await GameSessionRepository._invalidate_lookup_cache(
            access_token_hash=game_session.access_token_hash,
            refresh_token_hash=game_session.refresh_token_hash,
            client_token=game_session.client_token,
        )

    @classmethod
    async def revoke_by_access_token(
        cls,
        session: AsyncSession,
        access_token: str,
        client_token: str | None = None,
    ) -> int:
        access_token_hash = cls._token_hash(access_token)
        conditions: list[Column] = [
            cast(Column, GameSession.access_token_hash == access_token_hash)
        ]
        if client_token is not None:
            conditions.append(cast(Column, GameSession.client_token == client_token))

        select_stmt = select(GameSession).where(and_(*conditions))
        sessions_to_invalidate = list((await session.execute(select_stmt)).scalars().all())

        stmt = update(GameSession).where(and_(*conditions)).values(revoked=True)
        result = await session.execute(stmt)

        invalidate_tasks = [
            cls._invalidate_lookup_cache(
                access_token_hash=session_row.access_token_hash,
                refresh_token_hash=session_row.refresh_token_hash,
                client_token=session_row.client_token,
            )
            for session_row in sessions_to_invalidate
        ]
        invalidate_tasks.append(
            cls._invalidate_lookup_cache(
                access_token_hash=access_token_hash,
                client_token=client_token,
            )
        )
        await asyncio.gather(*invalidate_tasks)

        return result.rowcount if hasattr(result, "rowcount") else 0

    @staticmethod
    async def revoke_all_user_sessions(session: AsyncSession, user_id: UUID) -> int:
        select_stmt = select(GameSession).where(
            and_(
                cast(Column, GameSession.user_id == user_id),
                cast(Column, not_(GameSession.revoked)),
            )
        )
        sessions_to_invalidate = list((await session.execute(select_stmt)).scalars().all())

        stmt = (
            update(GameSession)
            .where(
                and_(
                    cast(Column, GameSession.user_id == user_id),
                    cast(Column, not_(GameSession.revoked)),
                )
            )
            .values(revoked=True)
        )
        result = await session.execute(stmt)

        if sessions_to_invalidate:
            await asyncio.gather(
                *[
                    GameSessionRepository._invalidate_lookup_cache(
                        access_token_hash=session_row.access_token_hash,
                        refresh_token_hash=session_row.refresh_token_hash,
                        client_token=session_row.client_token,
                    )
                    for session_row in sessions_to_invalidate
                ]
            )

        return result.rowcount if hasattr(result, "rowcount") else 0

    @classmethod
    async def mark_join(
        cls,
        session: AsyncSession,
        session_id: int,
        server_id: str,
        join_ip: str | None,
    ) -> None:
        session_stmt = select(GameSession).where(
            and_(
                cast(Column, GameSession.session_id == session_id),
                cast(Column, not_(GameSession.revoked)),
            )
        )
        game_session = (await session.execute(session_stmt)).scalar_one_or_none()
        if not game_session:
            return

        stmt = (
            update(GameSession)
            .where(
                and_(
                    cast(Column, GameSession.session_id == session_id),
                    cast(Column, not_(GameSession.revoked)),
                )
            )
            .values(
                joined_server_id=server_id,
                joined_at=func.now(),
                join_ip=join_ip,
                last_used_at=func.now(),
            )
        )
        await session.execute(stmt)
        await cls._invalidate_lookup_cache(
            access_token_hash=game_session.access_token_hash,
            refresh_token_hash=game_session.refresh_token_hash,
            client_token=game_session.client_token,
        )

    @staticmethod
    async def get_joined_user(
        session: AsyncSession,
        username: str,
        server_id: str,
        joined_after: datetime,
        ip: str | None = None,
    ) -> User | None:
        joined_at_column = cast(Column, GameSession.joined_at)
        conditions: list[Column] = [
            cast(Column, User.login == username),
            cast(Column, GameSession.joined_server_id == server_id),
            cast(Column, joined_at_column.is_not(None)),
            cast(Column, joined_at_column >= joined_after),
            cast(Column, not_(GameSession.revoked)),
            cast(Column, GameSession.access_expires_at > func.now()),
        ]
        if ip is not None:
            conditions.append(
                cast(Column, or_(GameSession.join_ip == ip, GameSession.ip_address == ip))
            )

        stmt = (
            select(User)
            .join(GameSession, cast(Column, GameSession.user_id == User.user_id))
            .where(and_(*conditions))
            .order_by(desc(joined_at_column))
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
