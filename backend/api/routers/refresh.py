from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi_limiter.depends import RateLimiter
from loguru import logger

from backend.api.dependencies.auth import AuthRefreshTokenDependency
from backend.api.exceptions import build_error_responses
from backend.api.exceptions.auth import AuthRefreshTokenRevokedException
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.schemas.auth import AuthPayload, Token, TokenType
from backend.api.schemas.login import LoginResponse
from backend.config import api_config, auth_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user_session import UserSessionRepository
from backend.redis.cache.session_cache_service import SessionCacheService
from backend.utils.auth import AuthService
from backend.utils.encryption import EncryptionService
from backend.utils.request_meta import get_client_ip, get_user_agent

router = APIRouter(tags=["refresh"])


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Refresh access token",
    responses=build_error_responses(
        *AuthRefreshTokenDependency.exceptions,
        LimitTooManyRequestsException,
    ),
    dependencies=[Depends(RateLimiter(times=10, seconds=30))],
)
async def refresh_token(
    raw_request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    token_data: tuple[Token, str] = Depends(AuthRefreshTokenDependency.get_token),
) -> LoginResponse:
    """
    Refresh the access token using the refresh token from cookies.

    Implements Token Rotation with Reuse Detection:
    - Issues a NEW refresh token with FULL N-day TTL
    - If old token is reused → revokes entire session (security breach)

    Args:
        raw_request (Request): The HTTP request.
        response (Response): The HTTP response to set cookies.
        background_tasks: Background tasks manager.
        token_data: Tuple of (decoded_token, refresh_token_value).

    Raises:
        AuthRefreshTokenNotFoundException: If refresh_token cookie is missing.
        AuthTokenExpiredException: If the token has expired.
        AuthTokenInvalidException: If the token is invalid.
        AuthInvalidTokenTypeException: If the token is not a refresh token.
        AuthRefreshTokenRevokedException: If the token is revoked, expired, or reused.

    Returns:
        LoginResponse: Contains the new access token.
    """
    decoded_token, refresh_token_value = token_data
    user_agent = get_user_agent(raw_request)
    ip_address = get_client_ip(raw_request)

    logger.debug(f"Refresh from IP '{ip_address}' with device info '{user_agent}'")

    payload = AuthPayload(
        user_id=decoded_token.user_id,
        email=decoded_token.email,
        login=decoded_token.login,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    new_access_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.access_token_lifetime,
        token_type=TokenType.access,
    )

    new_refresh_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.refresh_token_lifetime,
        token_type=TokenType.refresh,
    )

    rotation_success = await SessionCacheService.rotate_refresh_token(
        user_id=decoded_token.user_id,
        old_refresh_token=refresh_token_value,
        new_refresh_token=new_refresh_token,
        ttl=auth_settings.refresh_token_lifetime,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    if not rotation_success:
        raise AuthRefreshTokenRevokedException()

    background_tasks.add_task(
        _update_token_in_audit_log,
        old_refresh_token=refresh_token_value,
        new_refresh_token=new_refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    response.set_cookie(
        **api_config.get_cookie_settings(
            key="refresh_token",
            value=new_refresh_token,
            max_age=int(auth_settings.refresh_token_lifetime.total_seconds()),
        )
    )

    expires_at = int(
        (AuthService.get_current_time() + auth_settings.access_token_lifetime).timestamp()
    )

    return LoginResponse(
        access_token=new_access_token, login=decoded_token.login, expires_at=expires_at
    )


async def _update_token_in_audit_log(
    old_refresh_token: str,
    new_refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    """
    Background task to update refresh token in PostgreSQL audit log.

    Records token rotation history for audit purposes.
    Note: PostgreSQL is NOT the source of truth - Redis is.

    Args:
        old_refresh_token: The old refresh token to find session
        new_refresh_token: The new refresh token to store
        user_agent: User agent string
        ip_address: IP address
    """
    async with DatabaseProvider.session_lifecycle() as session:
        old_token_hash = EncryptionService.sha256(old_refresh_token)

        user_session = await UserSessionRepository.get_by_refresh_token_hash(
            session=session,
            refresh_token_hash=old_token_hash,
        )

        if user_session:
            await UserSessionRepository.update_refresh_token(
                session=session,
                session_id=user_session.session_id,
                new_refresh_token=new_refresh_token,
                user_agent=user_agent,
                ip_address=ip_address,
                expires_at=auth_settings.get_refresh_token_expires_at(),
            )
            logger.debug(
                f"[Background/PostgreSQL] Token rotation logged for session_id={user_session.session_id}"
            )
        else:
            logger.debug(
                "[Background/PostgreSQL] Session not found in audit log for token rotation "
                "(may not have been created yet by login background task)"
            )
