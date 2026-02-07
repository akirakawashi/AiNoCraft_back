from math import ceil
from typing import Any

from fastapi import Request, Response
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.api.exceptions.limit import LimitTooManyRequestsException


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="API_", env_file=".env", case_sensitive=False, extra="ignore"
    )

    path: str = Field(default="/api/v1", description="Base API path")
    secure: bool = Field(default=False, description="Use secure cookies")
    dev_mode: bool = Field(default=False, description="Development mode")

    def get_cookie_settings(self, key: str, value: str, max_age: int) -> dict[str, Any]:
        return dict(
            key=key,
            value=value,
            max_age=max_age,
            httponly=True,
            secure=self.secure,
            samesite="strict",
            path=self.path,
        )

    @staticmethod
    async def rate_limit_http_callback(request: Request, response: Response, pexpire: int) -> None:
        raise LimitTooManyRequestsException(retry_after=ceil(pexpire / 1000))


api_config = ApiConfig()
