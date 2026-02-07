from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPClientConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HTTP_CLIENT_", env_file=".env", case_sensitive=False, extra="ignore"
    )
    user_agent: str = Field(default="FastAPI backend", description="User agent string")
    timeout: int = Field(default=10, description="Request timeout in seconds")
    max_connections: int = Field(default=20, description="Maximum number of connections")
    max_keepalive_connections: int = Field(
        default=10, description="Maximum number of keepalive connections"
    )


http_client_config = HTTPClientConfig()
