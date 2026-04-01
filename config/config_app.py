from pydantic import BaseModel, Field
from pathlib import Path
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


class ServiceSettings(BaseModel):
    registration_open: bool = False
    new_devices_allowed: bool = False


class Secrets(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    service: ServiceSettings = Field(default_factory=ServiceSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


app_config = Secrets()
