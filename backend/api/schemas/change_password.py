from pydantic import BaseModel, Field, field_validator

from backend.api.exceptions.security import SecurityInvalidPasswordException


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(description="Old password")
    new_password: str = Field(description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, new_password: str) -> str:
        return SecurityInvalidPasswordException.validate_password(new_password)


class ChangePasswordResponse(BaseModel):
    status: bool = Field(description="True if password changed, False otherwise")
    message: str = Field(description="Message")
