from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.exceptions import build_error_responses
from backend.api.exceptions.auth import AuthInvalidCredentialsException
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.exceptions.user import UserNotFoundException
from backend.api.schemas.auth import AuthPayload, TokenType
from backend.api.schemas.login import LoginRequest, LoginResponse
from backend.config import api_config, auth_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories import UserRepository
from backend.database.repositories.user_session import UserSessionRepository
from backend.redis.cache.session_cache_service import SessionCacheService
from backend.utils.auth import AuthService
from backend.utils.encryption import EncryptionService
from backend.utils.request_meta import get_client_ip, get_user_agent

router = APIRouter(tags=["login"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login a user",
    responses=build_error_responses(
        AuthInvalidCredentialsException, UserNotFoundException, LimitTooManyRequestsException
    ),
    dependencies=[Depends(RateLimiter(times=10, seconds=30))],
)
async def login(
    request: LoginRequest,
    raw_request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> LoginResponse:
    """
    Authenticate a user and generate access and refresh tokens.

    Args:
        request (LoginRequest): User credentials (login and password).
        raw_request (Request): The raw HTTP request.
        response (Response): The HTTP response to set cookies.
        session (AsyncSession): The database session.

    Raises:
        AuthInvalidCredentialsException: If the login or password is incorrect.
        UserNotFoundException: If the user is not found.

    Returns:
        LoginResponse: Contains the access token.
    """
    user = await UserRepository.get_user_by_login(session=session, login=request.login)

    user_agent = get_user_agent(raw_request)
    ip_address = get_client_ip(raw_request)

    logger.debug(
        f"Login attempt for user '{request.login}' from IP '{ip_address}' with device info '{user_agent}'"
    )

    if not user:
        logger.info(f"Login failed: user '{request.login}' not found")
        raise UserNotFoundException()

    if not EncryptionService.verify_password(
        plain_password=request.password,
        hashed_password=user.password,
    ):
        logger.info(
            f"Login failed: invalid password for user '{request.login}' (id={user.user_id})"
        )
        raise AuthInvalidCredentialsException()

    logger.info(f"Login successful for user '{user.login}' (id={user.user_id})")
    payload = AuthPayload(
        user_id=user.user_id,
        email=user.email,
        login=user.login,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    access_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.access_token_lifetime,
        token_type=TokenType.access,
    )

    refresh_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.refresh_token_lifetime,
        token_type=TokenType.refresh,
    )

    # Delete old sessions from the same device (Redis cleanup)
    await SessionCacheService.delete_user_device_sessions(
        user_id=user.user_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Generate deterministic family_id based on user + device + IP
    session_family_id = SessionCacheService.generate_session_family_id(
        user_id=user.user_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Store new refresh token in Redis
    await SessionCacheService.store_refresh_token(
        user_id=user.user_id,
        refresh_token=refresh_token,
        ttl=auth_settings.refresh_token_lifetime,
        session_family_id=session_family_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Add session management to background tasks (PostgreSQL audit log only)
    background_tasks.add_task(
        _manage_user_session,
        user_id=user.user_id,
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    response.set_cookie(
        **api_config.get_cookie_settings(
            key="refresh_token",
            value=refresh_token,
            max_age=int(auth_settings.refresh_token_lifetime.total_seconds()),
        ),
    )

    expires_at = int(
        (AuthService.get_current_time() + auth_settings.access_token_lifetime).timestamp()
    )

    return LoginResponse(
        access_token=access_token,
        login=user.login,
        expires_at=expires_at,
    )


async def _manage_user_session(
    user_id: UUID,
    refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> None:
    """
    Background task to manage PostgreSQL audit log.

    PostgreSQL stores session history for UI display and analytics.
    This is NOT used for session validation - Redis is the Source of Truth.

    Args:
        user_id: The user ID
        refresh_token: The refresh token (for hash storage)
        user_agent: The user agent string
        ip_address: The IP address of the client
    """
    async with DatabaseProvider.session_lifecycle() as session:
        logger.debug(f"[Background/PostgreSQL] Recording login history for user_id={user_id}...")

        # Mark old sessions as revoked in audit log
        revoked_sessions = await UserSessionRepository.revoke_current_sessions(
            session=session, user_id=user_id, user_agent=user_agent, ip_address=ip_address
        )
        logger.debug(
            f"[Background/PostgreSQL] Marked {revoked_sessions} old sessions as revoked in audit log"
        )
        refresh_token_hash = EncryptionService.sha256(refresh_token)
        logger.debug(f"[Background/PostgreSQL] Creating audit log entry for user_id={user_id}")
        await UserSessionRepository.create_session(
            session=session,
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=auth_settings.get_refresh_token_expires_at(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        logger.debug(f"[Background/PostgreSQL] Audit log updated for user_id={user_id}")
