"""
Redis cache service for pending email-based actions.
Stores user data temporarily for registration and password-reset flows.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cashews import cache
from loguru import logger
from pydantic import BaseModel, ValidationError

from backend.api.exceptions.email import EmailCodeExpiredException, EmailInvalidCodeException
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.schemas.shared import PendingUserData
from backend.redis.cache.keyspace import CacheKeyspace
from backend.utils.encryption import EncryptionService

PENDING_EMAIL_CACHE = CacheKeyspace.from_prefix("pending")
PENDING_EMAIL_COOLDOWN_CACHE = CacheKeyspace.from_prefix("cooldown")
RESET_TOKEN_CACHE = CacheKeyspace.from_prefix("reset:user").scope("{user_id}", "token")
PENDING_EMAIL_TEMPLATE = "{email}"
RESET_TOKEN_TEMPLATE = "{token_hash}"


class ResetTokenData(BaseModel):
    """Data structure for password reset token stored in Redis."""

    user_id: UUID
    token_hash: str
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: str


class PendingEmailCacheService:
    """
    Handles temporary storage of pending email-based actions
    (for example: new-user registration and email-based password reset).
    """

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.lower().strip()

    @classmethod
    def _get_pending_key(cls, email: str) -> str:
        """
        Generate Redis key for pending user action.
        Key format: pending:{email}
        """
        return PENDING_EMAIL_CACHE.key(PENDING_EMAIL_TEMPLATE, email=cls._normalize_email(email))

    @classmethod
    def _get_cooldown_key(cls, email: str) -> str:
        """
        Generate Redis key for registration cooldown tracking.
        Key format: cooldown:{email}
        """
        return PENDING_EMAIL_COOLDOWN_CACHE.key(
            PENDING_EMAIL_TEMPLATE,
            email=cls._normalize_email(email),
        )

    @classmethod
    def _get_reset_token_key(cls, user_id: UUID, token_hash: str) -> str:
        """
        Generate Redis key for password reset tokens.
        Key format: reset:user:{user_id}:token:{token_hash}
        """
        return RESET_TOKEN_CACHE.key(
            RESET_TOKEN_TEMPLATE,
            user_id=user_id,
            token_hash=token_hash,
        )

    @staticmethod
    def _parse_pending_user_data(raw_data: object) -> PendingUserData | None:
        """Parse raw Redis data into PendingUserData model."""
        if not raw_data:
            return None
        # If already a PendingUserData instance, return as-is
        if isinstance(raw_data, PendingUserData):
            return raw_data
        if not isinstance(raw_data, dict):
            return None
        try:
            return PendingUserData.model_validate(raw_data)
        except ValidationError as e:
            logger.warning(f"[PendingEmailAction] Failed to parse pending user data: {e}")
            return None

    @staticmethod
    def _parse_reset_token_data(raw_data: object) -> ResetTokenData | None:
        """Parse raw Redis data into ResetTokenData model."""
        if not raw_data:
            return None
        # If already a ResetTokenData instance, return as-is
        if isinstance(raw_data, ResetTokenData):
            return raw_data
        if not isinstance(raw_data, dict):
            return None
        try:
            return ResetTokenData.model_validate(raw_data)
        except ValidationError as e:
            logger.warning(f"[PendingEmailAction] Failed to parse reset token data: {e}")
            return None

    @classmethod
    async def check_cooldown(cls, email: str) -> None:
        """
        Check if a cooldown is active for the given email.
        Raises LimitTooManyRequestsException if cooldown is active.
        """
        cooldown_key = cls._get_cooldown_key(email)
        has_cooldown = await cache.exists(cooldown_key)

        if has_cooldown:
            ttl = await cache.get_expire(cooldown_key)
            raise LimitTooManyRequestsException(retry_after=int(ttl) if ttl else 0)

    @classmethod
    async def store_pending_user(
        cls,
        email: str,
        pending_user_data: PendingUserData,
        ttl: int = 600,
        cooldown: int = 30,
    ) -> None:
        pending_key = cls._get_pending_key(email)
        cooldown_key = cls._get_cooldown_key(email)

        await asyncio.gather(
            cache.set(pending_key, pending_user_data, expire=ttl),
            cache.set(cooldown_key, True, expire=cooldown),
        )

        logger.debug(f"[PendingEmailAction] Stored pending action for email={email}, ttl={ttl}s")

    @classmethod
    async def get_pending_user(cls, email: str) -> PendingUserData | None:
        """
        Retrieve pending action data strictly for viewing/debugging.
        For verification logic, use `validate_code()` or other consuming flows.
        """
        pending_key = cls._get_pending_key(email)
        return cls._parse_pending_user_data(await cache.get(pending_key))

    @classmethod
    async def validate_code(cls, email: str, code: str) -> None:
        """
        Check if the code matches WITHOUT deleting the data.
        Useful if you have a multi-step process.
        """
        pending_key = cls._get_pending_key(email)
        pending_user_data = cls._parse_pending_user_data(await cache.get(pending_key))

        if not pending_user_data:
            logger.debug(f"[PendingEmailAction] No pending action found for {email}")
            raise EmailCodeExpiredException()

        if pending_user_data.verification_code != code:
            logger.warning(f"[PendingEmailAction] Invalid verification code attempt for {email}")
            raise EmailInvalidCodeException()

    @classmethod
    async def delete_pending_user(cls, email: str) -> None:
        """
        Remove data from Redis after successful DB write.
        """
        key = cls._get_pending_key(email)
        await cache.delete(key)
        logger.debug(f"[PendingEmailAction] Cleaned up pending action for {email}")

    @classmethod
    async def store_reset_token(
        cls,
        user_id: UUID,
        reset_token: str,
        ttl: timedelta,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Store a password reset token in Redis.

        Args:
            user_id: The user ID
            reset_token: The actual reset token (will be hashed for key)
            ttl: Time to live for the token
            user_agent: User agent string
            ip_address: IP address
        """
        token_hash = EncryptionService.sha256(reset_token)
        key = cls._get_reset_token_key(user_id, token_hash)

        reset_data = ResetTokenData(
            user_id=user_id,
            token_hash=token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=datetime.now(UTC).isoformat(),
        )

        ttl_seconds = int(ttl.total_seconds())
        await cache.set(key, reset_data, expire=ttl_seconds)
        logger.debug(
            f"[PendingEmailAction] Stored reset token for user_id={user_id}, ttl={ttl_seconds}s"
        )

    @classmethod
    async def verify_reset_token(cls, user_id: UUID, reset_token: str) -> bool:
        """
        Verify if reset token exists in Redis.

        Args:
            user_id: The user ID
            reset_token: The actual reset token (will be hashed for key)
        """
        token_hash = EncryptionService.sha256(reset_token)
        key = cls._get_reset_token_key(user_id, token_hash)
        reset_data = cls._parse_reset_token_data(await cache.get(key))

        if not reset_data:
            logger.debug(f"[PendingEmailAction] No valid reset token for user_id={user_id}")
            return False
        return True

    @classmethod
    async def delete_reset_token(cls, user_id: UUID, reset_token: str) -> None:
        """
        Delete reset token from Redis.

        Args:
            user_id: The user ID
            reset_token: The actual reset token (will be hashed for key)
        """
        token_hash = EncryptionService.sha256(reset_token)
        key = cls._get_reset_token_key(user_id, token_hash)
        await cache.delete(key)
        logger.debug(f"[PendingEmailAction] Deleted reset token for user_id={user_id}")

    @classmethod
    async def get_reset_token_ttl(cls, user_id: UUID, reset_token: str) -> int | None:
        """
        Get remaining TTL (time to live) in seconds for reset token.

        Args:
            user_id: The user ID
            reset_token: The actual reset token (will be hashed for key)
        Returns:
            Remaining TTL in seconds, or None if token not found
        """
        token_hash = EncryptionService.sha256(reset_token)
        key = cls._get_reset_token_key(user_id, token_hash)
        ttl_seconds = await cache.get_expire(key)

        if ttl_seconds and ttl_seconds > 0:
            result = int(ttl_seconds)
            logger.debug(f"[PendingEmailAction] Reset token TTL for user_id={user_id}: {result}s")
            return result

        logger.debug(f"[PendingEmailAction] No valid reset token found for user_id={user_id}")
        return None
