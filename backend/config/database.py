from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_", env_file=".env", case_sensitive=False, extra="ignore"
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(default="postgres", description="Database user")
    password: SecretStr = Field(default=SecretStr("postgres"), description="Database password")
    database: str = Field(default="postgres", description="Database name")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Maximum overflow connections")

    @property
    def async_url(self):
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"


db_settings = DatabaseConfig()
