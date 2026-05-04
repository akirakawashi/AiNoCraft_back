import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import AuthAccessTokenDependency, AuthRefreshTokenDependency
from backend.api.exceptions import build_error_responses
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.exceptions.security import (
    SecurityIncorrectOldPasswordException,
    SecurityInvalidPasswordException,
    SecuritySamePasswordException,
)
from backend.api.exceptions.user import UserNotFoundException
from backend.api.schemas.change_password import ChangePasswordRequest, ChangePasswordResponse
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user import UserRepository
from backend.database.repositories.user_session import UserSessionRepository
from backend.redis.cache.session_cache_service import SessionCacheService
from backend.utils.auth.jwt_service import Token
from backend.utils.encryption import EncryptionService

router = APIRouter(tags=["change_password"])


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change password",
    dependencies=[
        Depends(RateLimiter(times=10, seconds=30))
    ],  # TODO: Resolve password change rate limit
    responses=build_error_responses(
        LimitTooManyRequestsException,
        SecurityIncorrectOldPasswordException,
        SecuritySamePasswordException,
        SecurityInvalidPasswordException,
        *AuthAccessTokenDependency.exceptions,
        *AuthRefreshTokenDependency.exceptions,
    ),
)
async def change_password(
    request: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    # Use both token validation for security
    access_token: Token = Depends(AuthAccessTokenDependency.get_token),  # noqa: F841
    refresh_token_data: tuple[Token, str] = Depends(AuthRefreshTokenDependency.get_token),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> ChangePasswordResponse:
    """
    Change the password of a user.

    Args:
        request (ChangePasswordRequest): The data of the user to change the password.
        background_tasks (BackgroundTasks): FastAPI background tasks manager.
        access_token (Token): The access token of the user.
        refresh_token_data (tuple[Token, str]): The refresh token data of the user.
        session (AsyncSession): The database session.

    Raises:
        LimitTooManyRequestsException: If the rate limit is exceeded.
        SecurityIncorrectOldPasswordException: If the old password is incorrect.
        SecuritySamePasswordException: If the new password is the same as the old one.
        SecurityInvalidPasswordException: If the new password is invalid.
        *AuthAccessTokenDependency.exceptions: If the access token is invalid.
        *AuthRefreshTokenDependency.exceptions: If the refresh token is invalid.
        UserNotFoundException: If the user is not found.

    Returns:
        ChangePasswordResponse: The response of the password change.
    """
    decoded_token, refresh_token_value = refresh_token_data

    user = await UserRepository.get_user_by_login(session=session, login=decoded_token.login)

    if not user:
        raise UserNotFoundException()

    # Old password verification
    if not EncryptionService.verify_password(
        plain_password=request.old_password, hashed_password=user.password
    ):
        raise SecurityIncorrectOldPasswordException()

    # New password must be different from the old one
    if EncryptionService.verify_password(
        plain_password=request.new_password, hashed_password=user.password
    ):
        raise SecuritySamePasswordException()

    (
        delete_refresh_token_result,
        delete_all_user_sessions_result,
        change_user_password_result,
    ) = await asyncio.gather(
        SessionCacheService.delete_refresh_token(
            user_id=decoded_token.user_id, refresh_token=refresh_token_value
        ),
        SessionCacheService.delete_all_user_sessions(user_id=decoded_token.user_id),
        UserRepository.change_user_password(
            session=session,
            login=decoded_token.login,
            new_password=request.new_password,
        ),
        return_exceptions=True,
    )

    if isinstance(delete_refresh_token_result, Exception):
        logger.exception(
            f"[Redis] Failed to delete refresh token for user_id={decoded_token.user_id}:"
        )
        raise delete_refresh_token_result

    if isinstance(delete_all_user_sessions_result, Exception):
        logger.exception(
            f"[Redis] Failed to delete all user sessions for user_id={decoded_token.user_id}:"
        )
        raise delete_all_user_sessions_result

    if isinstance(change_user_password_result, Exception):
        logger.exception(
            f"[PostgreSQL] Failed to change password for user_id={decoded_token.user_id}:"
        )
        raise change_user_password_result

    background_tasks.add_task(_update_user_sessions, user_id=decoded_token.user_id)

    return ChangePasswordResponse(status=True, message="Пароль успешно изменён!")


async def _update_user_sessions(
    user_id: UUID,
) -> None:
    """
    Background task to update all user sessions after password change.

    Records password change history for audit purposes.
    Note: PostgreSQL is NOT the source of truth - Redis is.

    Args:
        user_id: The user ID
    """
    async with DatabaseProvider.session_lifecycle() as session:
        logger.debug(f"[Background/PostgreSQL] Recording password change for user_id={user_id}...")

        revoked_sessions = await UserSessionRepository.revoke_all_sessions(
            session=session, user_id=user_id
        )
        logger.debug(
            f"[Background/PostgreSQL] Marked {revoked_sessions} old sessions as revoked in audit log after password change"
        )
