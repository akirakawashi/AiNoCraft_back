import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.auth import AuthPayload, TokenType
from backend.api.schemas.minecraft import (
    MinecraftAuthenticateRequest,
    MinecraftAuthResponse,
    MinecraftInvalidateRequest,
    MinecraftRefreshRequest,
    MinecraftSignoutRequest,
    MinecraftValidateRequest,
)
from backend.config import auth_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories.game_session import GameSessionRepository
from backend.database.repositories.user import UserRepository
from backend.utils.auth import AuthService
from backend.utils.encryption import EncryptionService
from backend.utils.minecraft_profile import MinecraftProfileService
from backend.utils.request_meta import get_client_ip, get_user_agent

router = APIRouter(prefix="/authserver", tags=["minecraft_auth"])


def yggdrasil_error(
    error: str,
    error_message: str,
    cause: str = "",
    status_code: int = 403,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "errorMessage": error_message,
            "cause": cause,
        },
    )


def build_auth_response(
    *,
    access_token: str,
    refresh_token: str,
    client_token: str,
    user,
    request_user: bool,
) -> MinecraftAuthResponse:
    profile = MinecraftProfileService.build_profile(user)
    return MinecraftAuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        clientToken=client_token,
        availableProfiles=[profile],
        selectedProfile=profile,
        user=MinecraftProfileService.build_user_info(user) if request_user else None,
    )


@router.post(
    "/authenticate",
    response_model=MinecraftAuthResponse,
    dependencies=[Depends(RateLimiter(times=20, seconds=60))],
)
async def minecraft_authenticate(
    request: MinecraftAuthenticateRequest,
    raw_request: Request,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> MinecraftAuthResponse | JSONResponse:
    user = await UserRepository.get_user_by_login(session=session, login=request.username)
    if not user or not EncryptionService.verify_password(
        plain_password=request.password,
        hashed_password=user.password,
    ):
        return yggdrasil_error(
            error="ForbiddenOperationException",
            error_message="Invalid credentials. Invalid username or password.",
        )

    user_agent = get_user_agent(raw_request)
    ip_address = get_client_ip(raw_request)

    payload = AuthPayload(
        user_id=user.user_id,
        email=user.email,
        login=user.login,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    access_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.game_access_token_lifetime,
        token_type=TokenType.game_access,
    )
    refresh_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.game_refresh_token_lifetime,
        token_type=TokenType.game_refresh,
    )

    client_token = request.clientToken or MinecraftProfileService.create_client_token()
    await GameSessionRepository.create_session(
        session=session,
        user_id=user.user_id,
        client_token=client_token,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=auth_settings.get_game_access_token_expires_at(),
        refresh_expires_at=auth_settings.get_game_refresh_token_expires_at(),
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return build_auth_response(
        access_token=access_token,
        refresh_token=refresh_token,
        client_token=client_token,
        user=user,
        request_user=request.requestUser,
    )


@router.post(
    "/refresh",
    response_model=MinecraftAuthResponse,
    dependencies=[Depends(RateLimiter(times=30, seconds=60))],
)
async def minecraft_refresh(
    request: MinecraftRefreshRequest,
    raw_request: Request,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> MinecraftAuthResponse | JSONResponse:
    if not request.refreshToken and not request.accessToken:
        return yggdrasil_error(
            error="IllegalArgumentException",
            error_message="Either refreshToken or accessToken must be provided.",
            status_code=400,
        )

    game_session = None
    decoded_token = None

    if request.refreshToken:
        try:
            decoded_token = AuthService.validate_token(request.refreshToken)
        except jwt.InvalidTokenError:
            return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

        if decoded_token.type != TokenType.game_refresh:
            return yggdrasil_error("ForbiddenOperationException", "Invalid token type.")

        game_session = await GameSessionRepository.get_valid_by_refresh_token(
            session=session,
            refresh_token=request.refreshToken,
            client_token=request.clientToken,
        )
    elif request.accessToken:
        try:
            decoded_token = AuthService.validate_token(request.accessToken)
        except jwt.InvalidTokenError:
            return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

        if decoded_token.type != TokenType.game_access:
            return yggdrasil_error("ForbiddenOperationException", "Invalid token type.")

        game_session = await GameSessionRepository.get_valid_by_access_token(
            session=session,
            access_token=request.accessToken,
            client_token=request.clientToken,
        )

    if not decoded_token or not game_session:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")
    if game_session.session_id is None:
        return yggdrasil_error("ForbiddenOperationException", "Invalid session.")

    user = await UserRepository.get_user_by_login(session=session, login=decoded_token.login)
    if not user:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    if request.selectedProfile and request.selectedProfile.id != user.user_id.hex:
        return yggdrasil_error(
            "IllegalArgumentException", "Invalid selected profile.", status_code=400
        )

    user_agent = get_user_agent(raw_request)
    ip_address = get_client_ip(raw_request)

    payload = AuthPayload(
        user_id=user.user_id,
        email=user.email,
        login=user.login,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    new_access_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.game_access_token_lifetime,
        token_type=TokenType.game_access,
    )
    new_refresh_token = AuthService.create_token(
        payload=payload,
        expires_delta=auth_settings.game_refresh_token_lifetime,
        token_type=TokenType.game_refresh,
    )

    await GameSessionRepository.rotate_tokens(
        session=session,
        session_id=game_session.session_id,
        new_access_token=new_access_token,
        new_refresh_token=new_refresh_token,
        access_expires_at=auth_settings.get_game_access_token_expires_at(),
        refresh_expires_at=auth_settings.get_game_refresh_token_expires_at(),
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return build_auth_response(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        client_token=game_session.client_token,
        user=user,
        request_user=request.requestUser,
    )


@router.post(
    "/validate",
    status_code=204,
    response_model=None,
    dependencies=[Depends(RateLimiter(times=60, seconds=60))],
)
async def minecraft_validate(
    request: MinecraftValidateRequest,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> Response | JSONResponse:
    try:
        decoded_token = AuthService.validate_token(request.accessToken)
    except jwt.InvalidTokenError:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    if decoded_token.type != TokenType.game_access:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token type.")

    game_session = await GameSessionRepository.get_valid_by_access_token(
        session=session,
        access_token=request.accessToken,
        client_token=request.clientToken,
    )
    if not game_session:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    return Response(status_code=204)


@router.post(
    "/invalidate",
    status_code=204,
    response_model=None,
    dependencies=[Depends(RateLimiter(times=30, seconds=60))],
)
async def minecraft_invalidate(
    request: MinecraftInvalidateRequest,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> Response | JSONResponse:
    if request.accessToken:
        await GameSessionRepository.revoke_by_access_token(
            session=session,
            access_token=request.accessToken,
            client_token=request.clientToken,
        )
        return Response(status_code=204)

    if request.refreshToken:
        game_session = await GameSessionRepository.get_valid_by_refresh_token(
            session=session,
            refresh_token=request.refreshToken,
            client_token=request.clientToken,
        )
        if game_session and game_session.session_id:
            await GameSessionRepository.revoke_session(
                session=session, session_id=game_session.session_id
            )
        return Response(status_code=204)

    return yggdrasil_error(
        error="IllegalArgumentException",
        error_message="accessToken or refreshToken is required.",
        status_code=400,
    )


@router.post(
    "/signout",
    status_code=204,
    response_model=None,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def minecraft_signout(
    request: MinecraftSignoutRequest,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> Response | JSONResponse:
    user = await UserRepository.get_user_by_login(session=session, login=request.username)
    if not user or not EncryptionService.verify_password(
        plain_password=request.password,
        hashed_password=user.password,
    ):
        return yggdrasil_error(
            error="ForbiddenOperationException",
            error_message="Invalid credentials. Invalid username or password.",
        )

    await GameSessionRepository.revoke_all_user_sessions(session=session, user_id=user.user_id)
    return Response(status_code=204)
