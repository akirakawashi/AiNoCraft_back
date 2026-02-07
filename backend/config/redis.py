from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_", env_file=".env", case_sensitive=False, extra="ignore"
    )

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: str = Field(default="", description="Redis password")

    @property
    def url(self):
        return f"redis://default:{self.password}@{self.host}:{self.port}/0"


redis_settings = DatabaseConfig()
