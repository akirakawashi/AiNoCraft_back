from pydantic import BaseModel, Field


class AvatarResponse(BaseModel):
    avatar_url: str = Field(description="Public URL to the avatar")


class AvatarUploadResponse(BaseModel):
    presigned_url: str = Field(description="Pre-signed URL")
    avatar_url: str = Field(description="Avatar URL in MinIO")


class AvatarCompleteResponse(BaseModel):
    message: str = Field(description="Completion message")
    success: bool = Field(description="Indicates if the avatar upload was successful")


class AvatarRequest(BaseModel):
    file_name: str = Field(description="Name of the file to be uploaded")
