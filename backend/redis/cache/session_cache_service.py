"""
Redis cache service for user sessions (Source of Truth).

This module manages active refresh tokens in Redis.
Redis is the single source of truth for session validity.
If a token doesn't exist in Redis, the session is invalid.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cashews import cache
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from backend.redis.cache.keyspace import CacheKeyspace
from backend.utils.encryption import EncryptionService

SESSION_CACHE = CacheKeyspace.from_prefix("session:user")
SESSION_TOKEN_CACHE = SESSION_CACHE.scope("{user_id}", "token")
SESSION_FAMILY_CACHE = SESSION_CACHE.scope("{user_id}", "family")
SESSION_TOKEN_TEMPLATE = "{token_hash}"
SESSION_FAMILY_TEMPLATE = "{session_family_id}"
SESSION_ALL_TOKENS_TEMPLATE = "*"
SESSION_ALL_FAMILIES_TEMPLATE = "*"


class SessionData(BaseModel):
    """Data structure for a single session token stored in Redis."""

    user_id: UUID
    token_hash: str
    session_family_id: str
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: str


class SessionFamilyData(BaseModel):
    """Data structure for session family metadata stored in Redis."""

    tokens: list[str] = Field(default_factory=list)
    current_token: str | None = None
    updated_at: str | None = None


class SessionCacheService:
    """
    Redis-based session cache service with Token Rotation and Reuse Detection.

    Redis stores active refresh tokens with automatic expiration.
    This is the authoritative source for session validity checks.

    Token Rotation Strategy:
    - Each session family tracks the current active token
    - Only the current token is valid for use
    - If any other token (old/stolen) is presented → revoke entire session family
    """

    @classmethod
    def _get_token_key(cls, user_id: UUID, token_hash: str) -> str:
        """
        Generate Redis key for a refresh token.

        Args:
            user_id: The user ID
            token_hash: The hashed refresh token

        Returns:
            Redis key string
        """
        return SESSION_TOKEN_CACHE.key(
            SESSION_TOKEN_TEMPLATE,
            user_id=user_id,
            token_hash=token_hash,
        )

    @classmethod
    def _get_user_sessions_pattern(cls, user_id: UUID) -> str:
        """
        Generate Redis pattern to match all sessions for a user.

        Args:
            user_id: The user ID

        Returns:
            Redis pattern string
        """
        return SESSION_TOKEN_CACHE.key(
            SESSION_ALL_TOKENS_TEMPLATE,
            user_id=user_id,
        )

    @classmethod
    def _get_session_family_key(cls, user_id: UUID, session_family_id: str) -> str:
        """
        Generate Redis key for tracking all tokens in a session family.

        Session family = all tokens generated from the same initial login.
        Used for revoking entire chain when reuse is detected.

        Args:
            user_id: The user ID
            session_family_id: Unique identifier for the session family

        Returns:
            Redis key string
        """
        return SESSION_FAMILY_CACHE.key(
            SESSION_FAMILY_TEMPLATE,
            user_id=user_id,
            session_family_id=session_family_id,
        )

    @classmethod
    def _get_session_family_key_pattern(cls, user_id: UUID) -> str:
        """
        Generate Redis pattern to match all session families for a user.

        Args:
            user_id: The user ID

        Returns:
            Redis pattern string
        """
        return SESSION_FAMILY_CACHE.key(
            SESSION_ALL_FAMILIES_TEMPLATE,
            user_id=user_id,
        )

    @staticmethod
    def _parse_session_data(raw_data: object) -> SessionData | None:
        """Parse raw Redis data into SessionData model."""
        if not raw_data:
            return None
        # If already a SessionData instance, return as-is
        if isinstance(raw_data, SessionData):
            return raw_data
        if not isinstance(raw_data, dict):
            return None
        try:
            return SessionData.model_validate(raw_data)
        except ValidationError as e:
            logger.warning(f"[Redis] Failed to parse session data: {e}")
            return None

    @staticmethod
    def _parse_family_data(raw_data: object) -> SessionFamilyData | None:
        """Parse raw Redis data into SessionFamilyData model."""
        if not raw_data:
            return None
        # If already a SessionFamilyData instance, return as-is
        if isinstance(raw_data, SessionFamilyData):
            return raw_data
        if not isinstance(raw_data, dict):
            return None
        try:
            return SessionFamilyData.model_validate(raw_data)
        except ValidationError as e:
            logger.warning(f"[Redis] Failed to parse session family data: {e}")
            return None

    @staticmethod
    def generate_session_family_id(
        user_id: UUID, user_agent: str | None, ip_address: str | None
    ) -> str:
        """
        Generate deterministic session family ID based on user + device + IP.

        Same device always gets the same family ID, ensuring tokens from
        the same device belong to the same rotation chain.

        Args:
            user_id: The user ID
            user_agent: User agent string
            ip_address: IP address

        Returns:
            Deterministic family ID (hash of user + device + IP)
        """
        # Create unique identifier for this device
        device_signature = f"{user_id}:{user_agent or 'unknown'}:{ip_address or 'unknown'}"
        return EncryptionService.sha256(device_signature)

    @classmethod
    async def store_refresh_token(
        cls,
        user_id: UUID,
        refresh_token: str,
        ttl: timedelta,
        session_family_id: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Store a refresh token in Redis (Source of Truth).

        Args:
            user_id: The user ID
            refresh_token: The actual refresh token (will be hashed for key)
            ttl: Time to live for the token
            session_family_id: Unique ID for the session family (chain of rotated tokens)
            user_agent: User agent string
            ip_address: IP address
        """
        token_hash = EncryptionService.sha256(refresh_token)
        key = cls._get_token_key(user_id, token_hash)

        session_data = SessionData(
            user_id=user_id,
            token_hash=token_hash,
            session_family_id=session_family_id,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=datetime.now(UTC).isoformat(),
        )

        # Prepare session family metadata
        family_key = cls._get_session_family_key(user_id, session_family_id)
        family_data = cls._parse_family_data(await cache.get(family_key))

        # Initialize if family doesn't exist
        if not family_data:
            family_data = SessionFamilyData()

        # Add token to history
        if token_hash not in family_data.tokens:
            family_data.tokens.append(token_hash)

        # Mark as current active token
        family_data.current_token = token_hash
        family_data.updated_at = datetime.now(UTC).isoformat()

        # Save both token and family in parallel
        await asyncio.gather(
            cache.set(key, session_data, expire=ttl),
            cache.set(family_key, family_data, expire=ttl),
        )

        logger.debug(
            f"[Redis] Stored refresh token for user_id={user_id}, "
            f"family_id={session_family_id}, ttl={ttl.total_seconds()}s"
        )

    @classmethod
    async def _verify_token_is_current(
        cls, user_id: UUID, token_hash: str, session_family_id: str
    ) -> bool:
        """
        Check if token is the current active token in its family.

        Args:
            user_id: The user ID
            token_hash: The token hash to verify
            session_family_id: The session family ID

        Returns:
            True if token is current, False if not current or family not found
        """
        family_key = cls._get_session_family_key(user_id, session_family_id)
        family_data = cls._parse_family_data(await cache.get(family_key))

        if not family_data:
            logger.warning(
                f"[Redis] Session family '{session_family_id}' not found for user_id={user_id}"
            )
            return False

        if family_data.current_token != token_hash:
            logger.error(
                f"🚨 [SECURITY] Non-current token usage detected for user_id={user_id}! "
                f"Current: {family_data.current_token[:8] if family_data.current_token else 'None'}..., "
                f"Provided: {token_hash[:8]}... "
                f"This indicates token theft (old/stolen token reuse)."
            )
            # Revoke entire session family
            await cls.revoke_session_family(user_id, session_family_id)
            return False

        return True

    @classmethod
    async def verify_refresh_token(cls, user_id: UUID, refresh_token: str) -> SessionData | None:
        """
        Verify if a refresh token is valid and current.

        This is the Source of Truth check - if token is not in Redis,
        it's invalid regardless of what's in PostgreSQL.

        Security: Checks if token is the CURRENT token in session family.
        Any non-current token (old/stolen) triggers session revocation.

        Args:
            user_id: The user ID
            refresh_token: The refresh token to verify

        Returns:
            SessionData if valid and current, None if invalid/stale
        """
        token_hash = EncryptionService.sha256(refresh_token)
        key = cls._get_token_key(user_id, token_hash)

        session_data = cls._parse_session_data(await cache.get(key))
        if not session_data:
            logger.debug(f"[Redis] Token not found or expired for user_id={user_id}")
            return None

        # Verify token is current in its family
        if not await cls._verify_token_is_current(
            user_id, token_hash, session_data.session_family_id
        ):
            return None  # Non-current token - security breach

        logger.debug(f"[Redis] Valid current token found for user_id={user_id}")
        return session_data

    @classmethod
    async def get_refresh_token_ttl(cls, user_id: UUID, refresh_token: str) -> int | None:
        """
        Get remaining TTL (time to live) in seconds for a refresh token.

        Args:
            user_id: The user ID
            refresh_token: The refresh token

        Returns:
            Remaining TTL in seconds, or None if token not found
        """
        token_hash = EncryptionService.sha256(refresh_token)
        key = cls._get_token_key(user_id, token_hash)

        ttl_seconds = await cache.get_expire(key)
        if ttl_seconds and ttl_seconds > 0:
            result = int(ttl_seconds)
            logger.debug(f"[Redis] Token TTL for user_id={user_id}: {result}s")
            return result
        else:
            logger.debug(f"[Redis] Token TTL not found for user_id={user_id}")
            return None

    @classmethod
    async def delete_refresh_token(cls, user_id: UUID, refresh_token: str) -> bool:
        """
        Delete a specific refresh token from Redis (logout/revoke).

        Args:
            user_id: The user ID
            refresh_token: The refresh token to delete

        Returns:
            True if token was deleted, False if not found
        """
        token_hash = EncryptionService.sha256(refresh_token)
        key = cls._get_token_key(user_id, token_hash)

        deleted = await cache.delete(key)
        if deleted:
            logger.debug(f"[Redis] Deleted token for user_id={user_id}")
        else:
            logger.debug(f"[Redis] Token not found for deletion, user_id={user_id}")
        return deleted

    @classmethod
    async def delete_user_device_sessions(
        cls, user_id: UUID, user_agent: str | None, ip_address: str | None
    ) -> int:
        """
        Delete all sessions for a specific device (user_agent + ip_address).

        This ensures only one active session per device/IP combination.
        Used during login to remove old sessions from the same device.

        Args:
            user_id: The user ID
            user_agent: User agent string to match
            ip_address: IP address to match

        Returns:
            Number of sessions deleted
        """
        pattern = cls._get_user_sessions_pattern(user_id)

        # Collect all matching keys first
        keys_to_delete = []
        async for key, raw_data in cache.get_match(pattern):
            session_data = cls._parse_session_data(raw_data)
            if session_data:
                if session_data.user_agent == user_agent and session_data.ip_address == ip_address:
                    keys_to_delete.append(key)

        # Delete all collected keys in one batch operation
        if keys_to_delete:
            await cache.delete_many(*keys_to_delete)
            logger.debug(
                f"[Redis] Deleted {len(keys_to_delete)} old session(s) for user_id={user_id}, "
                f"device='{user_agent}', ip='{ip_address}'"
            )

        return len(keys_to_delete)

    @classmethod
    async def delete_all_user_sessions(cls, user_id: UUID) -> None:
        """
        Delete all refresh tokens for a user (logout from all devices).

        Args:
            user_id: The user ID

        Returns:
            Number of tokens deleted
        """
        session_pattern = cls._get_user_sessions_pattern(user_id)
        family_pattern = cls._get_session_family_key_pattern(user_id)
        await asyncio.gather(
            cache.delete_match(session_pattern), cache.delete_match(family_pattern)
        )
        logger.debug(f"[Redis] Deleted all sessions for user_id={user_id}")

    @classmethod
    async def rotate_refresh_token(
        cls,
        user_id: UUID,
        old_refresh_token: str,
        new_refresh_token: str,
        ttl: timedelta,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """
        Rotate refresh token with Reuse Detection support.

        Strategy:
        1. Check if old token is valid and not used
        2. Verify old token is current in session family
        2. Delete old token from Redis
        3. Store new token and update family's current_token
        4. If old token is not current → security breach → revoke family

        Args:
            user_id: The user ID
            old_refresh_token: The old refresh token to rotate
            new_refresh_token: The new refresh token to issue
            ttl: Time to live for new token
            user_agent: User agent string
            ip_address: IP address

        Returns:
            True if rotation successful, False if security breach detected
        """
        old_token_hash = EncryptionService.sha256(old_refresh_token)
        old_key = cls._get_token_key(user_id, old_token_hash)

        # Get old token data
        old_session_data = cls._parse_session_data(await cache.get(old_key))

        if not old_session_data:
            logger.warning(f"[Redis] Cannot rotate: old token not found for user_id={user_id}")
            return False

        session_family_id = old_session_data.session_family_id

        # Verify token is current in family (REUSE DETECTION)
        if not await cls._verify_token_is_current(user_id, old_token_hash, session_family_id):
            return False  # Security breach detected (already logged and revoked)

        # Delete old token and store new one in parallel
        await asyncio.gather(
            cache.delete(old_key),
            cls.store_refresh_token(
                user_id=user_id,
                refresh_token=new_refresh_token,
                ttl=ttl,
                session_family_id=session_family_id,
                user_agent=user_agent,
                ip_address=ip_address,
            ),
        )

        logger.info(
            f"✅ [Redis] Token rotation successful for user_id={user_id}, "
            f"family_id={session_family_id}, new_ttl={ttl.total_seconds()}s"
        )
        return True

    @classmethod
    async def revoke_session_family(cls, user_id: UUID, session_family_id: str) -> int:
        """
        Revoke all tokens in a session family (used when reuse is detected).

        This logs out the user from the entire session chain, forcing re-login.

        Args:
            user_id: The user ID
            session_family_id: The session family ID to revoke

        Returns:
            Number of tokens revoked
        """
        family_key = cls._get_session_family_key(user_id, session_family_id)
        family_data = cls._parse_family_data(await cache.get(family_key))

        if not family_data:
            logger.debug(f"[Redis] Session family '{session_family_id}' not found")
            return 0

        sessions = [cls._get_token_key(user_id, token_hash) for token_hash in family_data.tokens]

        # Delete all tokens in family and family metadata in parallel
        await asyncio.gather(
            cache.delete_many(*sessions),
            cache.delete(family_key),
        )

        logger.warning(
            f"[Redis] Revoked session family '{session_family_id}' for user_id={user_id}, "
            f"deleted {len(sessions)} tokens"
        )
        return len(sessions)
