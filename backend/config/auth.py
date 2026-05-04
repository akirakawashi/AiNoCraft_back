import re
from datetime import UTC, datetime, timedelta

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_duration(value: str | int | float | timedelta) -> timedelta:
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    if isinstance(value, str):
        value = value.strip().lower()
        match = re.fullmatch(r"(\d+)([smhd])", value)
        if match:
            num, unit = match.groups()
            num = int(num)
            if unit == "s":
                return timedelta(seconds=num)
            if unit == "m":
                return timedelta(minutes=num)
            if unit == "h":
                return timedelta(hours=num)
            if unit == "d":
                return timedelta(days=num)
        # fallback: try to parse as seconds
        try:
            return timedelta(seconds=float(value))
        except Exception:
            pass
    raise ValueError(f"Invalid duration: {value}")


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_", env_file=".env", case_sensitive=False, extra="ignore"
    )

    secret_key: SecretStr = Field(description="Auth secret key")
    algorithm: str = Field(default="HS256", description="Auth algorithm")
    access_token_lifetime: timedelta = Field(
        default=timedelta(minutes=15), description="Access token lifetime"
    )
    refresh_token_lifetime: timedelta = Field(
        default=timedelta(days=30), description="Refresh token lifetime"
    )
    reset_password_token_lifetime: timedelta = Field(
        default=timedelta(minutes=10), description="Password reset token lifetime"
    )
    game_access_token_lifetime: timedelta = Field(
        default=timedelta(days=1), description="Game access token lifetime"
    )
    game_refresh_token_lifetime: timedelta = Field(
        default=timedelta(days=30), description="Game refresh token lifetime"
    )
    game_join_ttl: timedelta = Field(
        default=timedelta(seconds=60), description="TTL for join -> hasJoined handshake"
    )

    @field_validator(
        "access_token_lifetime",
        "refresh_token_lifetime",
        "reset_password_token_lifetime",
        "game_access_token_lifetime",
        "game_refresh_token_lifetime",
        "game_join_ttl",
        mode="before",
    )
    @classmethod
    def parse_timedelta(cls, v):
        return parse_duration(v)

    def get_access_token_expires_at(self) -> datetime:
        """Get access token expiration time from current moment"""
        return datetime.now(tz=UTC) + self.access_token_lifetime

    def get_refresh_token_expires_at(self) -> datetime:
        """Get refresh token expiration time from current moment"""
        return datetime.now(tz=UTC) + self.refresh_token_lifetime

    def get_reset_password_token_expires_at(self) -> datetime:
        """Get reset password token expiration time from current moment"""
        return datetime.now(tz=UTC) + self.reset_password_token_lifetime

    def get_game_access_token_expires_at(self) -> datetime:
        """Get game access token expiration time from current moment"""
        return datetime.now(tz=UTC) + self.game_access_token_lifetime

    def get_game_refresh_token_expires_at(self) -> datetime:
        """Get game refresh token expiration time from current moment"""
        return datetime.now(tz=UTC) + self.game_refresh_token_lifetime


auth_settings = AuthConfig()  # type: ignore
