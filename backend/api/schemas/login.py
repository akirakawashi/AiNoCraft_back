from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(description="User login")
    password: str = Field(description="User password")


class LoginResponse(BaseModel):
    access_token: str = Field(description="Access token")
    login: str = Field(description="User login")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: int = Field(description="Access token expiration as UNIX timestamp (seconds)")
