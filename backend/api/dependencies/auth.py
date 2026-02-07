from datetime import UTC, datetime

import jwt
from fastapi import Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.exceptions.auth import (
    AuthAccessTokenNotFoundException,
    AuthInvalidTokenTypeException,
    AuthPasswordResetTokenNotFoundException,
    AuthRefreshTokenNotFoundException,
    AuthRefreshTokenRevokedException,
    AuthTokenExpiredException,
    AuthTokenInvalidException,
)
from backend.api.exceptions.user import UserNotFoundException
from backend.api.schemas.auth import Token, TokenType
from backend.database.provider import DatabaseProvider
from backend.database.repositories.user import UserRepository
from backend.redis.cache import PendingEmailCacheService, SessionCacheService
from backend.utils.auth import AuthService


class AuthRefreshTokenDependency:
    exceptions = {
        AuthRefreshTokenNotFoundException,
        AuthRefreshTokenRevokedException,
        AuthTokenExpiredException,
        AuthTokenInvalidException,
        AuthInvalidTokenTypeException,
    }

    @staticmethod
    async def get_token(raw_request: Request) -> tuple[Token, str]:
        """
        Retrieves the refresh token from the refresh_token cookie and validates it.

        Args:
            raw_request (Request): The HTTP request containing the refresh_token cookie.

        Returns:
            tuple[Token, str, timedelta]: A tuple containing the decoded token, the refresh token value,
            and the remaining lifetime of the token.

        Raises:
            AuthRefreshTokenNotFoundException: If the refresh_token cookie is missing.
            AuthTokenExpiredException: If the refresh token has expired.
            AuthTokenInvalidException: If the refresh token is invalid.
            AuthInvalidTokenTypeException: If the token is not a refresh token.
            AuthRefreshTokenRevokedException: If the token is not found in Redis or has expired.
        """
        refresh_token_value = raw_request.cookies.get("refresh_token")
        if not refresh_token_value:
            logger.info("Refresh failed: refresh_token cookie not found")
            raise AuthRefreshTokenNotFoundException()
        try:
            decoded_token = AuthService.validate_token(refresh_token_value)
        except jwt.ExpiredSignatureError:
            logger.info("Refresh failed: token expired")
            raise AuthTokenExpiredException()
        except jwt.InvalidTokenError:
            logger.info("Refresh failed: invalid token")
            raise AuthTokenInvalidException()
        except Exception:
            logger.exception("Refresh failed: unexpected error during token validation")
            raise AuthTokenInvalidException()

        if decoded_token.type != TokenType.refresh:
            logger.info("Refresh failed: token is not a refresh token")
            raise AuthInvalidTokenTypeException()

        session_data = await SessionCacheService.verify_refresh_token(
            user_id=decoded_token.user_id,
            refresh_token=refresh_token_value,
        )

        if not session_data:
            logger.info(
                f"Refresh failed: token not found in Redis for user_id={decoded_token.user_id}"
            )
            raise AuthRefreshTokenRevokedException()

        remaining_ttl_seconds = await SessionCacheService.get_refresh_token_ttl(
            user_id=decoded_token.user_id,
            refresh_token=refresh_token_value,
        )

        if not remaining_ttl_seconds:
            logger.warning(
                f"Could not get TTL for refresh token, user_id={decoded_token.user_id}. "
                "Token may have expired."
            )
            raise AuthRefreshTokenRevokedException()

        return decoded_token, refresh_token_value


class AuthAccessTokenDependency:
    exceptions = {
        AuthAccessTokenNotFoundException,
        AuthInvalidTokenTypeException,
        AuthTokenExpiredException,
        AuthTokenInvalidException,
        UserNotFoundException,
    }

    @staticmethod
    async def get_token(
        raw_request: Request, session: AsyncSession = Depends(DatabaseProvider.get_session)
    ) -> Token:
        """
        Retrieves the access token from the Authorization header and validates it.

        Args:
            raw_request: The HTTP request containing the Authorization header.

        Returns:
            Token: The decoded access token.

        Raises:
            AuthAccessTokenNotFoundException: If the access token is missing from the Authorization header.
            AuthInvalidTokenTypeException: If the token type is not access.
            AuthTokenExpiredException: If the access token has expired.
            AuthTokenInvalidException: If the access token is invalid.
        """
        try:
            access_token = raw_request.headers.get("Authorization", "").split(
                "Bearer ", maxsplit=1
            )[1]

        except Exception:
            raise AuthAccessTokenNotFoundException()
        else:
            if not access_token:
                raise AuthAccessTokenNotFoundException()
        try:
            decoded_token = AuthService.validate_token(access_token)
        except jwt.ExpiredSignatureError:
            logger.debug("Access token has expired")
            raise AuthTokenExpiredException()
        except jwt.InvalidTokenError:
            logger.debug("Access token is invalid")
            raise AuthTokenInvalidException()
        except Exception:
            logger.exception("Access token validation error")
            raise AuthTokenInvalidException()

        if decoded_token.type != TokenType.access:
            raise AuthInvalidTokenTypeException()

        user = await UserRepository.get_user_by_login(session=session, login=decoded_token.login)

        if not user:
            raise UserNotFoundException()

        if user.password_change_date and user.password_change_date >= datetime.fromtimestamp(
            decoded_token.iat, UTC
        ):
            raise AuthTokenExpiredException()

        return decoded_token


class AuthPasswordResetTokenDependency:
    exceptions = {
        AuthPasswordResetTokenNotFoundException,
        AuthTokenExpiredException,
        AuthTokenInvalidException,
        AuthInvalidTokenTypeException,
    }

    @staticmethod
    async def get_token(raw_request: Request) -> tuple[Token, str]:
        """
        Retrieves the password reset token from the password_reset_token cookie and validates it.

        Args:
            raw_request (Request): The HTTP request containing the password_reset_token cookie.

        Returns:
            tuple[Token, str]: The decoded password reset token and the raw token string.
        Raises:
            AuthPasswordResetTokenNotFoundException: If the password_reset_token cookie is missing.
            AuthTokenExpiredException: If the password reset token has expired.
            AuthTokenInvalidException: If the password reset token is invalid.
            AuthInvalidTokenTypeException: If the token is not a password reset token.
        """
        reset_password_token = raw_request.cookies.get("reset_password_token")
        if not reset_password_token:
            logger.debug("Password reset failed: reset_password_token cookie not found")
            raise AuthPasswordResetTokenNotFoundException()
        try:
            decoded_token = AuthService.validate_token(reset_password_token)
        except jwt.ExpiredSignatureError:
            logger.debug("Password reset failed: token expired")
            raise AuthTokenExpiredException()
        except jwt.InvalidTokenError:
            logger.debug("Password reset failed: invalid token")
            raise AuthTokenInvalidException()
        except Exception:
            logger.exception("Password reset failed: unexpected error during token validation")
            raise AuthTokenInvalidException()

        if decoded_token.type != TokenType.reset:
            logger.debug("Password reset failed: token is not a reset token")
            raise AuthInvalidTokenTypeException()

        if not await PendingEmailCacheService.verify_reset_token(
            user_id=decoded_token.user_id,
            reset_token=reset_password_token,
        ):
            logger.debug(
                f"Password reset failed: token not found in Redis for user_id={decoded_token.user_id}"
            )
            raise AuthTokenExpiredException()

        if not await PendingEmailCacheService.get_reset_token_ttl(
            user_id=decoded_token.user_id,
            reset_token=reset_password_token,
        ):
            logger.debug(
                f"Password reset failed: token expired for user_id={decoded_token.user_id}"
            )
            raise AuthTokenExpiredException()

        return decoded_token, reset_password_token
