from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MinioConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINIO_", env_file=".env", case_sensitive=False, extra="ignore"
    )
    endpoint: str = Field(default="localhost:9000", description="MinIO server endpoint")
    access_key: str = Field(..., description="MinIO access key")
    secret_key: str = Field(..., description="MinIO secret key")
    secure: bool = Field(default=False, description="Use secure connection (HTTPS)")
    presigned_url_lifetime: int = Field(default=5, description="Presigned URL lifetime in minutes")
    public_url: str = Field(
        default="https://storage.ainocraft.com",
        description="Public URL for MinIO (e.g., storage.ainocraft.com)",
    )


minio_settings = MinioConfig()  # type: ignore
