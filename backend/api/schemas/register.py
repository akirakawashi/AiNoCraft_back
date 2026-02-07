import re

from pydantic import BaseModel, EmailStr, field_validator

from backend.api.exceptions.security import SecurityInvalidPasswordException


class RegisterRequest(BaseModel):
    login: str
    email: EmailStr
    password: str

    @field_validator("login")
    @classmethod
    def validate_username(cls, username: str) -> str:
        if 3 > len(username) > 20:
            raise ValueError("Username length must be between 3 and 20 characters")
        if not re.match(r"^[a-zA-Z0-9]+$", username):
            raise ValueError("Username must contain only letters and numbers")
        return username

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        return SecurityInvalidPasswordException.validate_password(password)


class RegisterResponse(BaseModel):
    message: str
    login: str
    email: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendCodeRequest(BaseModel):
    email: EmailStr
