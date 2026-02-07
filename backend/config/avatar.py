from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AvatarConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AVATAR_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    bucket_name: str = Field(default="avatars", description="MinIO bucket name for storing avatars")
    allowed_types: list = Field(
        default=["jpg", "png", "webp", "jpeg"],
        description="Allowed file extensions for avatar uploads",
    )
    allowed_mime_types: list = Field(
        default=["image/jpeg", "image/png", "image/webp"],
        description="Allowed MIME types for avatar uploads",
    )
    max_size: int = Field(
        default=5 * 1024 * 1024, description="Maximum allowed size for avatar uploads in bytes"
    )


avatar_config = AvatarConfig()
