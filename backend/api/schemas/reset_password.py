from pydantic import BaseModel, Field


class ResetPasswordInitRequest(BaseModel):
    email: str = Field(description="The email address of the user requesting a password reset.")


class ResetPasswordVerificationRequest(ResetPasswordInitRequest):
    code: str = Field(description="The verification code sent to the user's email.")


class ResetPasswordFinalizeRequest(BaseModel):
    new_password: str = Field(description="The new password to set for the user.")


class ResetPasswordResponse(BaseModel):
    status: bool = Field(description="True if the password reset was successful, False otherwise.")
    message: str = Field(
        description="A message providing additional information about the password reset process."
    )
    email: str = Field(description="The email address associated with the password reset request.")
