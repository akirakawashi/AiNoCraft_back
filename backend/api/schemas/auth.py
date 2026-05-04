from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field


class AuthPayload(BaseModel):
    user_id: UUID = Field(description="User ID")
    email: str = Field(description="User email")
    login: str = Field(description="User login")
    user_agent: str | None = Field(description="User agent")
    ip_address: str | None = Field(description="IP address")


class Token(AuthPayload):
    type: str = Field(description="Token type")
    iat: float = Field(description="Issued at")
    exp: float = Field(description="Expiration time")


@dataclass
class TokenType:
    access: str = "access"
    refresh: str = "refresh"
    reset: str = "reset"
    game_access: str = "game_access"
    game_refresh: str = "game_refresh"
