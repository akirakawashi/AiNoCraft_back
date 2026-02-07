import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import AuthPasswordResetTokenDependency
from backend.api.exceptions import build_error_responses
from backend.api.exceptions.email import EmailCodeExpiredException, EmailInvalidCodeException
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.exceptions.security import SecurityInvalidPasswordException
from backend.api.exceptions.user import UserNotFoundException
from backend.api.schemas.auth import AuthPayload, Token, TokenType
from backend.api.schemas.reset_password import (
    ResetPasswordFinalizeRequest,
    ResetPasswordInitRequest,
    ResetPasswordResponse,
    ResetPasswordVerificationRequest,
)
from backend.api.schemas.shared import PendingUserData
from backend.config import api_config, auth_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user import UserRepository
from backend.database.repositories.user_session import UserSessionRepository
from backend.redis.cache import PendingEmailCacheService, SessionCacheService
from backend.smtp.email_service import EmailService
from backend.utils.auth import AuthService
from backend.utils.code_verify import generate_verification_code

router = APIRouter(prefix="/reset-password", tags=["reset_password"])


@router.post(
    "/init",
    response_model=ResetPasswordResponse,
    summary="Initiate password reset process",
    dependencies=[Depends(RateLimiter(times=2, seconds=60))],
    responses=build_error_responses(UserNotFoundException, LimitTooManyRequestsException),
)
async def reset_password_init(
    request: ResetPasswordInitRequest,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> ResetPasswordResponse:
    """
    Initiates the password reset process by sending a verification code to the user's email.

    Args:
        request (ResetPasswordInitRequest): The data of the user to initiate the password reset process.
        session (AsyncSession): The database session.

    Raises:
        UserNotFoundException: If the user is not found.
        LimitTooManyRequestsException: If the rate limit is exceeded.

    Returns:
        ResetPasswordResponse: The response of the password reset initiation.
    """
    user = await UserRepository.get_user_by_email(session=session, email=request.email)

    if not user:
        raise UserNotFoundException()

    verification_code = generate_verification_code()

    pending_user_data = PendingUserData(
        id_=user.user_id,
        login=user.login,
        email=user.email,
        verification_code=verification_code,
    )

    await asyncio.gather(
        PendingEmailCacheService.store_pending_user(
            email=user.email,
            pending_user_data=pending_user_data,
        ),
        EmailService.send_password_reset_code(
            email=pending_user_data.email,
            username=pending_user_data.login,
            code=pending_user_data.verification_code,
        ),
    )

    logger.debug(f"Email with verification code sent to: {request.email}")

    return ResetPasswordResponse(
        message="Код подтверждения отправлен на почту",
        email=request.email,
        status=True,
    )


@router.post(
    "/verify",
    response_model=ResetPasswordResponse,
    summary="Initiate password reset process",
    dependencies=[Depends(RateLimiter(times=2, seconds=60))],
    responses=build_error_responses(
        UserNotFoundException,
        LimitTooManyRequestsException,
        EmailCodeExpiredException,
        EmailInvalidCodeException,
    ),
)
async def reset_password_verify(
    request: ResetPasswordVerificationRequest,
    response: Response,
    raw_request: Request,
    background_tasks: BackgroundTasks,
) -> ResetPasswordResponse:
    """
    Initiate password reset process.

    Args:
        request: ResetPasswordVerificationRequest - containing email and verification code.
        response: Response - the HTTP response to set cookies.
        raw_request: Request - the raw HTTP request.
        background_tasks: BackgroundTasks - tasks to be run in the background.

    Raises:
        UserNotFoundException: If the user is not found.
        LimitTooManyRequestsException: If the rate limit is exceeded.
        EmailCodeExpiredException: If the verification code is expired.
        EmailInvalidCodeException: If the verification code is invalid.

    Returns:
        ResetPasswordResponse: Contains the reset password token.
    """
    user_agent = raw_request.headers.get("user-agent")
    ip_address = raw_request.client.host if raw_request.client else None

    logger.debug(
        f"Password reset attempt for email '{request.email}' from IP '{ip_address}' with device info '{user_agent}'"
    )

    await PendingEmailCacheService.validate_code(request.email, request.code)

    pending_user_data = await PendingEmailCacheService.get_pending_user(request.email)

    if not pending_user_data:
        raise EmailCodeExpiredException()

    if not pending_user_data.id_:
        raise UserNotFoundException()

    # Invalidate all existing sessions
    await SessionCacheService.delete_all_user_sessions(pending_user_data.id_)

    background_tasks.add_task(
        _revoke_all_sessions,
        user_id=pending_user_data.id_,
    )

    payload = AuthPayload(
        user_id=pending_user_data.id_,
        email=pending_user_data.email,
        login=pending_user_data.login,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    reset_password_token = AuthService.create_token(
        payload=payload,
        token_type=TokenType.reset,
        expires_delta=auth_settings.reset_password_token_lifetime,
    )

    await asyncio.gather(
        PendingEmailCacheService.store_reset_token(
            user_id=pending_user_data.id_,
            reset_token=reset_password_token,
            ttl=auth_settings.reset_password_token_lifetime,
            user_agent=user_agent,
            ip_address=ip_address,
        ),
        PendingEmailCacheService.delete_pending_user(request.email),
    )

    response.set_cookie(
        **api_config.get_cookie_settings(
            key="reset_password_token",
            value=reset_password_token,
            max_age=int(auth_settings.reset_password_token_lifetime.total_seconds()),
        ),
    )

    return ResetPasswordResponse(
        message="Код подтвержден. Можно сбросить пароль.",
        email=request.email,
        status=True,
    )


@router.post(
    "/finalize",
    response_model=ResetPasswordResponse,
    summary="Initiate password reset process",
    dependencies=[Depends(RateLimiter(times=2, seconds=60))],
    responses=build_error_responses(
        *AuthPasswordResetTokenDependency.exceptions,
        UserNotFoundException,
        LimitTooManyRequestsException,
        SecurityInvalidPasswordException,
    ),
)
async def reset_password_finalize(
    request: ResetPasswordFinalizeRequest,
    response: Response,
    reset_token_data: tuple[Token, str] = Depends(AuthPasswordResetTokenDependency.get_token),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
):
    """
    Initiates the password reset process by setting a new password for the user.

    Args:
        request (ResetPasswordFinalizeRequest): The data of the user to finalize the password reset process.
        password_reset_token (Token): The password reset token.
        session (AsyncSession): The database session.

    Raises:
        *AuthPasswordResetTokenDependency.exceptions: If the password reset token is invalid.
        UserNotFoundException: If the user is not found.
        LimitTooManyRequestsException: If the rate limit is exceeded.
        SecurityInvalidPasswordException: If the new password is invalid.

    Returns:
        ResetPasswordResponse: The response of the password reset finalization.
    """
    reset_token, reset_token_value = reset_token_data
    user = await UserRepository.get_user_by_login(session=session, login=reset_token.login)

    if not user:
        raise UserNotFoundException()

    new_password = SecurityInvalidPasswordException.validate_password(request.new_password)

    updated_rows = await UserRepository.change_user_password(
        session=session, login=reset_token.login, new_password=new_password
    )

    # Clear the password reset token cookie
    response.delete_cookie(
        key="reset_password_token",
        path=api_config.path,
    )

    await PendingEmailCacheService.delete_reset_token(
        user_id=user.user_id,
        reset_token=reset_token_value,
    )

    if updated_rows > 0:
        logger.debug(
            f"Password reset successful for user_id={user.user_id}, login={user.login}, updated_rows={updated_rows}"
        )

        await EmailService.send_password_changed(
            email=user.email,
            username=user.login,
        )

        return ResetPasswordResponse(
            message="Пароль успешно изменён.",
            email=user.email,
            status=True,
        )

    else:
        logger.error(
            f"Password reset failed for user_id={user.user_id}, login={user.login}, updated_rows={updated_rows}"
        )
        return ResetPasswordResponse(
            message="Не удалось изменить пароль. Попробуйте еще раз.",
            email=user.email,
            status=False,
        )


async def _revoke_all_sessions(user_id: int):
    """
    Background task to revoke all sessions for a user during password reset.

    Args:
        user_id (int): The user ID
    """
    async with DatabaseProvider.session_lifecycle() as session:
        logger.debug(
            f"[Background/PostgreSQL] Revoking all sessions for user_id={user_id} during password reset..."
        )
        revoked_sessions = await UserSessionRepository.revoke_all_sessions(
            session=session, user_id=user_id
        )
        logger.debug(
            f"[Background/PostgreSQL] Successfully revoked {revoked_sessions} sessions for user_id={user_id} during password reset."
        )
