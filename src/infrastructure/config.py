from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str


class BotSettings(BaseModel):
    token: str
    bot_name: str
    admin_id: int


class PaymentSettings(BaseModel):
    payment_url: str
    payment_qr: str
    free_month: int


class LoggingSettings(BaseModel):
    log_level: str = "INFO"
    log_json: bool = False
    log_to_file: bool = False
    log_dir: Path = Path("logs")
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5


class AppConfig(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


app_config = AppConfig()
