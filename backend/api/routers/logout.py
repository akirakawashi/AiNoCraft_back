import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi_limiter.depends import RateLimiter
from loguru import logger

from backend.config.api import api_config
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user_session import UserSessionRepository
from backend.redis.cache.session_cache_service import SessionCacheService
from backend.utils.auth import AuthService
from backend.utils.encryption import EncryptionService

router = APIRouter(tags=["logout"])


@router.post(
    "/logout",
    summary="Logout user and revoke refresh token",
    dependencies=[Depends(RateLimiter(times=10, seconds=30))],
)
async def logout(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Logout user by:
    1. Deleting refresh token from Redis (Source of Truth) - immediate invalidation
    2. Marking session as revoked in PostgreSQL (audit log) - background task
    3. Clearing the refresh_token httpOnly cookie

    Args:
        request: The HTTP request to get the refresh token
        response: The HTTP response to clear cookies
        background_tasks: FastAPI background tasks

    Returns:
        dict[str, str]: Success message
    """
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    logger.debug(f"Logout attempt from IP '{ip_address}' with device info '{user_agent}'")

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            decoded_token = AuthService.validate_token(refresh_token)
            user_id = decoded_token.user_id

            # Delete from Redis immediately (Source of Truth)
            deleted = await SessionCacheService.delete_refresh_token(
                user_id=user_id,
                refresh_token=refresh_token,
            )

            if deleted:
                logger.debug(f"[Redis] Revoked refresh token for user_id={user_id}")

                # Mark as revoked in PostgreSQL audit log (background)
                background_tasks.add_task(
                    _revoke_session_in_audit_log,
                    refresh_token=refresh_token,
                )
            else:
                logger.debug(
                    f"[Redis] Token not found for user_id={user_id} (already expired/revoked)"
                )

        except jwt.InvalidTokenError:
            logger.warning("Logout: invalid refresh token, clearing cookie anyway")
        except Exception as e:
            logger.error(f"Logout: error processing token: {e}")
    else:
        logger.debug("Logout: no refresh_token cookie found")
        return {"message": "Not logged in"}

    # Delete refresh_token cookie regardless
    response.delete_cookie(
        key="refresh_token",
        path=api_config.path,
        samesite="strict",
    )

    return {"message": "Successfully logged out"}


async def _revoke_session_in_audit_log(refresh_token: str) -> None:
    """
    Background task to mark session as revoked in PostgreSQL audit log.

    Args:
        refresh_token: The refresh token to revoke
    """
    async with DatabaseProvider.session_lifecycle() as session:
        refresh_token_hash = EncryptionService.sha256(refresh_token)

        user_session = await UserSessionRepository.get_by_refresh_token_hash(
            session=session,
            refresh_token_hash=refresh_token_hash,
        )

        if user_session:
            await UserSessionRepository.revoke_session(
                session=session,
                session_id=user_session.session_id,
            )
            logger.debug(
                f"[Background/PostgreSQL] Marked session_id={user_session.session_id} "
                f"as revoked in audit log"
            )
        else:
            logger.debug("[Background/PostgreSQL] Session not found in audit log")
