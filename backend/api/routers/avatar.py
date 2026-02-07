from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter
from loguru import logger
from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import AuthAccessTokenDependency
from backend.api.exceptions.base import build_error_responses
from backend.api.exceptions.limit.exceptions import LimitTooManyRequestsException
from backend.api.exceptions.user import (
    UserAvatarFailedException,
    UserAvatarTooLargeException,
    UserAvatarUnsupportedTypeException,
    UserNotFoundException,
)
from backend.api.schemas.auth import Token
from backend.api.schemas.avatar import (
    AvatarCompleteResponse,
    AvatarRequest,
    AvatarResponse,
    AvatarUploadResponse,
)
from backend.config import avatar_config, minio_settings
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user import UserRepository
from backend.minio.provider import MinioProvider

router = APIRouter(prefix="/avatars", tags=["avatars"])


@router.post(
    "/get-upload-url",
    response_model=AvatarUploadResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    responses=build_error_responses(
        LimitTooManyRequestsException,
        *AuthAccessTokenDependency.exceptions,
        UserAvatarUnsupportedTypeException,
        UserAvatarFailedException,
    ),
)
async def get_avatar_upload_url(
    request: AvatarRequest,
    access_token: Token = Depends(AuthAccessTokenDependency.get_token),
    minio_signing_client: Minio = Depends(MinioProvider.get_signing_client),
) -> AvatarUploadResponse:
    user_id = access_token.user_id

    if len(request.file_name) == 0:
        logger.error("File name is empty")
        raise UserAvatarFailedException()

    ext = request.file_name.split(".")[-1].lower()
    if ext not in avatar_config.allowed_types:
        logger.error(f"Unsupported file type: {ext}")
        raise UserAvatarUnsupportedTypeException()

    avatar_filename = f"{uuid4()}.{ext}"
    avatar_minio_url = f"{user_id}/{avatar_filename}"

    presigned_url = minio_signing_client.get_presigned_url(
        "PUT",
        avatar_config.bucket_name,
        avatar_minio_url,
        expires=timedelta(minutes=minio_settings.presigned_url_lifetime),
    )

    return AvatarUploadResponse(presigned_url=presigned_url, avatar_url=avatar_filename)


@router.post(
    "/avatar-complete",
    response_model=AvatarCompleteResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    responses=build_error_responses(
        *AuthAccessTokenDependency.exceptions,
        UserAvatarUnsupportedTypeException,
        UserAvatarFailedException,
        UserAvatarTooLargeException,
    ),
)
async def avatar_complete(
    request: AvatarRequest,
    access_token: Token = Depends(AuthAccessTokenDependency.get_token),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
    minio_client: Minio = Depends(MinioProvider.get_client),
) -> AvatarCompleteResponse:
    user_id = access_token.user_id
    login = access_token.login

    avatar_name = request.file_name
    avatar_minio_url = f"{user_id}/{avatar_name}"

    try:
        object_stat = minio_client.stat_object(avatar_config.bucket_name, avatar_minio_url)
    except S3Error:
        logger.exception("Failed to stat object in MinIO")
        raise UserAvatarFailedException()

    assert object_stat.size is not None

    if object_stat.content_type not in avatar_config.allowed_mime_types:
        logger.error(f"Unsupported file type: {object_stat.content_type}")
        minio_client.remove_object(avatar_config.bucket_name, avatar_minio_url)
        raise UserAvatarUnsupportedTypeException()

    if object_stat.size > avatar_config.max_size:
        logger.error(f"File size too large: {object_stat.size} bytes")
        minio_client.remove_object(avatar_config.bucket_name, avatar_minio_url)
        raise UserAvatarTooLargeException()

    cached_user = await UserRepository.get_user_by_login(session, login)
    old_avatar_name = cached_user.avatar_name if cached_user else None

    rows_updated = await UserRepository.update_avatar_url(
        session=session, login=login, avatar_name=avatar_name
    )
    if rows_updated == 0:
        logger.error(f"Failed to update avatar URL for login: {login}")
        minio_client.remove_object(avatar_config.bucket_name, avatar_minio_url)
        raise UserAvatarFailedException()

    if old_avatar_name:
        old_avatar_minio = f"{user_id}/{old_avatar_name}"
        try:
            minio_client.remove_object(avatar_config.bucket_name, old_avatar_minio)
            logger.debug(f"Old avatar removed: {old_avatar_name}")
        except S3Error:
            logger.warning(f"Failed to remove old avatar: {old_avatar_name}")

    logger.debug(f"[UPLOAD] Avatar URL updated for login: {login}, rows updated: {rows_updated}")

    return AvatarCompleteResponse(message="Avatar upload completed successfully", success=True)


@router.get(
    "/get-avatar",
    response_model=AvatarResponse,
    responses=build_error_responses(
        *AuthAccessTokenDependency.exceptions,
        UserAvatarFailedException,
        UserNotFoundException,
    ),
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def get_avatar(
    access_token: Token = Depends(AuthAccessTokenDependency.get_token),
    session: AsyncSession = Depends(DatabaseProvider.get_session),
) -> AvatarResponse:
    """Get presigned URL for avatar retrieval with authentication"""
    user_id = access_token.user_id
    login = access_token.login

    user = await UserRepository.get_user_by_login(session, login)
    if not user:
        logger.error(f"User not found: {login}")
        raise UserNotFoundException()

    if not user.avatar_name:
        logger.error(f"No avatar found for login: {login}")
        raise UserAvatarFailedException()

    full_avatar_url = (
        f"{minio_settings.public_url}/{avatar_config.bucket_name}/{user_id}/{user.avatar_name}"
    )

    return AvatarResponse(avatar_url=full_avatar_url)
