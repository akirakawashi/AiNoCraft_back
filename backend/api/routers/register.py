import asyncio

from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.exceptions import build_error_responses
from backend.api.exceptions.email import EmailCodeExpiredException, EmailInvalidCodeException
from backend.api.exceptions.limit import LimitTooManyRequestsException
from backend.api.exceptions.security import SecurityInvalidPasswordException
from backend.api.exceptions.user import (
    UserEmailAlreadyExistsException,
    UserLoginAlreadyExistsException,
)
from backend.api.schemas.register import (
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    VerifyEmailRequest,
)
from backend.api.schemas.shared import PendingUserData
from backend.database.provider import DatabaseProvider
from backend.database.repositories import UserRepository
from backend.redis.cache import PendingEmailCacheService
from backend.smtp.email_service import EmailService
from backend.utils.code_verify import generate_verification_code
from backend.utils.encryption import EncryptionService

router = APIRouter(prefix="/register", tags=["register"])


@router.post(
    "/init",
    response_model=RegisterResponse,
    summary="Register a new user",
    responses=build_error_responses(
        UserLoginAlreadyExistsException,
        UserEmailAlreadyExistsException,
        LimitTooManyRequestsException,
        SecurityInvalidPasswordException,
    ),
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def register_init(
    request: RegisterRequest, session: AsyncSession = Depends(DatabaseProvider.get_session)
):
    """
    Validate input, check duplicates, generate code, store in Redis.
    User is NOT created in DB yet.
    """
    await PendingEmailCacheService.check_cooldown(request.email)

    existing_user = await UserRepository.get_user_by_login(session, request.login)
    if existing_user:
        raise UserLoginAlreadyExistsException()

    existing_email = await UserRepository.get_user_by_email(session, request.email)
    if existing_email:
        raise UserEmailAlreadyExistsException()

    password = SecurityInvalidPasswordException.validate_password(request.password)
    hashed_password = EncryptionService.hash_password(password)

    code = generate_verification_code()

    pending_user_data = PendingUserData(
        login=request.login,
        email=request.email,
        password=hashed_password,
        verification_code=code,
    )

    await asyncio.gather(
        PendingEmailCacheService.store_pending_user(
            email=request.email,
            pending_user_data=pending_user_data,
        ),
        EmailService.send_verification(
            email=pending_user_data.email,
            username=pending_user_data.login,
            code=pending_user_data.verification_code,
        ),
    )

    logger.debug(f"Email with verification code sent to: {request.email}")

    return RegisterResponse(
        message="Код подтверждения отправлен на почту",
        login=request.login,
        email=request.email,
    )


@router.post(
    "/verify",
    response_model=RegisterResponse,
    summary="Verify email and complete registration",
    responses=build_error_responses(
        UserLoginAlreadyExistsException,
        EmailCodeExpiredException,
        EmailInvalidCodeException,
        LimitTooManyRequestsException,
        SecurityInvalidPasswordException,
    ),
    dependencies=[Depends(RateLimiter(times=6, seconds=60))],
)
async def register_verify(
    request: VerifyEmailRequest, session: AsyncSession = Depends(DatabaseProvider.get_session)
):
    """
    Verify the code sent to email and create the user in the database.
    """
    await PendingEmailCacheService.validate_code(request.email, request.code)

    pending_user_data = await PendingEmailCacheService.get_pending_user(request.email)
    if not pending_user_data:
        raise EmailCodeExpiredException()

    if await UserRepository.get_user_by_login(session, pending_user_data.login):
        raise UserLoginAlreadyExistsException()

    if not pending_user_data.password:
        # This should never happen
        logger.error(f"Pending user data for {request.email} is missing password hash")
        raise SecurityInvalidPasswordException()

    tasks = (
        UserRepository.create_user(
            session=session,
            login=pending_user_data.login,
            email=pending_user_data.email,
            password=pending_user_data.password,
        ),
        PendingEmailCacheService.delete_pending_user(request.email),
        EmailService.send_welcome(email=pending_user_data.email, username=pending_user_data.login),
    )

    await asyncio.gather(*tasks)

    return RegisterResponse(
        message="Почта подтверждена, аккаунт создан!",
        login=pending_user_data.login,
        email=pending_user_data.email,
    )


@router.post(
    "/resend-code",
    response_model=RegisterResponse,
    summary="Resend verification code to email",
    responses=build_error_responses(
        EmailCodeExpiredException,
        LimitTooManyRequestsException,
    ),
    dependencies=[Depends(RateLimiter(times=1, seconds=60))],
)
async def register_resend(
    request: ResendCodeRequest,
) -> RegisterResponse:
    """
    Generate new code for existing pending registration.
    """
    await PendingEmailCacheService.check_cooldown(request.email)

    pending_user_data = await PendingEmailCacheService.get_pending_user(request.email)
    if not pending_user_data:
        raise EmailCodeExpiredException()

    new_code = generate_verification_code()
    pending_user_data.verification_code = new_code

    await asyncio.gather(
        PendingEmailCacheService.store_pending_user(
            email=request.email,
            pending_user_data=pending_user_data,
        ),
        EmailService.send_verification(
            email=pending_user_data.email,
            username=pending_user_data.login,
            code=pending_user_data.verification_code,
        ),
    )

    logger.debug(f"Email with new verification code sent to: {request.email}")

    return RegisterResponse(
        message="Новый код подтверждения отправлен на почту",
        login=pending_user_data.login,
        email=pending_user_data.email,
    )
