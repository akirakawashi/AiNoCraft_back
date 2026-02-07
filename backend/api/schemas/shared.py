from pydantic import BaseModel, EmailStr, Field


class PendingUserData(BaseModel):
    id_: int | None = Field(default=None, description="User ID")
    login: str = Field(..., description="User's login name")
    email: EmailStr = Field(..., description="User's email address")
    password: str | None = Field(default=None, description="User's password")
    verification_code: str = Field(..., description="Verification code sent to email")
