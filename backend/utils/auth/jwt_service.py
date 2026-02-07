from datetime import UTC, datetime, timedelta
from typing import ClassVar

import jwt
from pydantic import SecretStr

from backend.api.schemas.auth import AuthPayload, Token
from backend.config import auth_settings


class AuthService:
    _secret_key: ClassVar[SecretStr] = auth_settings.secret_key
    algorithm: ClassVar[str] = auth_settings.algorithm

    @classmethod
    def get_current_time(cls) -> datetime:
        """
        Get current time in UTC.

        Note: In a real system with time synchronization via database,
        this would fetch the current time from the database.
        For now, we use system time, but the JWT timestamps use
        UNIX timestamps which are absolute and database-agnostic.
        """
        return datetime.now(tz=UTC)

    @classmethod
    def create_token(
        cls,
        payload: AuthPayload,
        expires_delta: timedelta,
        token_type: str,
    ) -> str:
        """
        Creates a JWT token with the given payload and expiration delta.

        Args:
            payload: The payload to be encoded in the JWT token.
            expires_delta: The timedelta representing the expiration time of the token.
            token_type: The type of the token (e.g. "access" or "refresh").

        Returns:
            str: The created JWT token.
        """
        now = cls.get_current_time()
        payload_dict = Token(
            user_id=payload.user_id,
            email=payload.email,
            login=payload.login,
            type=token_type,
            user_agent=payload.user_agent,
            ip_address=payload.ip_address,
            iat=now.timestamp(),
            exp=(now + expires_delta).timestamp(),
        ).model_dump()

        return jwt.encode(
            payload=payload_dict,
            key=cls._secret_key.get_secret_value(),
            algorithm=cls.algorithm,
        )

    @classmethod
    def validate_token(cls, token: str) -> Token:
        """
        Validates a JWT token and returns the payload as a Token object.

        Args:
            token: The JWT token to validate.

        Returns:
            Token: The payload of the token as a Token object.

        """
        payload = jwt.decode(
            token,
            key=cls._secret_key.get_secret_value(),
            algorithms=[cls.algorithm],
        )
        return Token.model_validate(payload, extra="forbid")
