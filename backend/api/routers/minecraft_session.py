from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routers.minecraft_auth import yggdrasil_error
from backend.api.schemas.auth import TokenType
from backend.api.schemas.minecraft import MinecraftHasJoinedResponse, MinecraftJoinRequest
from backend.config import auth_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories.game_session import GameSessionRepository
from backend.database.repositories.user import UserRepository
from backend.utils.auth import AuthService
from backend.utils.minecraft_profile import MinecraftProfileService
from backend.utils.request_meta import get_client_ip

router = APIRouter(prefix="/sessionserver/session/minecraft", tags=["minecraft_session"])


@router.post(
    "/join",
    status_code=204,
    response_model=None,
    dependencies=[Depends(RateLimiter(times=60, seconds=60))],
)
async def minecraft_join(
    request: MinecraftJoinRequest,
    raw_request: Request,
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> Response:
    try:
        decoded_token = AuthService.validate_token(request.accessToken)
    except jwt.InvalidTokenError:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    if decoded_token.type != TokenType.game_access:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token type.")

    game_session = await GameSessionRepository.get_valid_by_access_token(
        session=session,
        access_token=request.accessToken,
    )
    if not game_session or not game_session.session_id:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    user = await UserRepository.get_user_by_login(session=session, login=decoded_token.login)
    if not user:
        return yggdrasil_error("ForbiddenOperationException", "Invalid token.")

    if request.selectedProfile != user.user_id.hex:
        return yggdrasil_error(
            "IllegalArgumentException",
            "selectedProfile does not match authenticated user.",
            status_code=400,
        )

    join_ip = get_client_ip(raw_request)
    await GameSessionRepository.mark_join(
        session=session,
        session_id=game_session.session_id,
        server_id=request.serverId,
        join_ip=join_ip,
    )
    return Response(status_code=204)


@router.get(
    "/hasJoined",
    response_model=MinecraftHasJoinedResponse,
    dependencies=[Depends(RateLimiter(times=120, seconds=60))],
)
async def minecraft_has_joined(
    username: str = Query(...),
    serverId: str = Query(...),
    ip: str | None = Query(default=None),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> MinecraftHasJoinedResponse | Response:
    joined_after = datetime.now(tz=UTC) - auth_settings.game_join_ttl
    user = await GameSessionRepository.get_joined_user(
        session=session,
        username=username,
        server_id=serverId,
        joined_after=joined_after,
        ip=ip,
    )
    if not user:
        return Response(status_code=204)

    return MinecraftHasJoinedResponse(
        id=user.user_id.hex,
        name=user.login,
        properties=MinecraftProfileService.build_properties(user),
    )


@router.get(
    "/profile/{stripped_uuid}",
    response_model=MinecraftHasJoinedResponse,
    dependencies=[Depends(RateLimiter(times=120, seconds=60))],
)
async def minecraft_profile_by_uuid(
    stripped_uuid: str,
    unsigned: bool = Query(default=True),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> MinecraftHasJoinedResponse | Response:
    """
    Return profile data by UUID (without dashes).

    `unsigned` is accepted for Yggdrasil compatibility.
    """
    _ = unsigned

    try:
        user_id = UUID(stripped_uuid)
    except ValueError:
        return Response(status_code=204)

    user = await UserRepository.get_user_by_id(session=session, user_id=user_id)
    if not user:
        return Response(status_code=204)

    return MinecraftHasJoinedResponse(
        id=user.user_id.hex,
        name=user.login,
        properties=MinecraftProfileService.build_properties(user),
    )
