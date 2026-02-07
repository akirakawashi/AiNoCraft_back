from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SmtpConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMTP_", env_file=".env", case_sensitive=False, extra="ignore"
    )

    host: str = Field(default="localhost", description="SMTP server host")
    port: int = Field(default=465, description="SMTP server port")
    username: str = Field(description="SMTP username")
    password: str = Field(description="SMTP password")
    from_email: str = Field(default="noreply@example.com", description="Sender email address")
    from_name: str = Field(default="AiNoCraft", description="Sender name")
    use_tls: bool = Field(default=True, description="Use TLS for SMTP connection")
    timeout: int = Field(default=10, description="SMTP connection timeout in seconds")
    template_dir: str = Field(
        default="backend/smtp/templates/", description="Path to email templates"
    )
    keep_alive_interval: int = Field(default=120, description="SMTP keep-alive interval in seconds")
    pool_size: int = Field(default=2, description="SMTP connection pool size")
    noop_timeout: int = Field(default=10, description="SMTP NOOP command timeout in seconds")
    max_retries: int = Field(
        default=3, description="Maximum number of retries for SMTP reconnection"
    )


smtp_settings = SmtpConfig()  # type: ignore
