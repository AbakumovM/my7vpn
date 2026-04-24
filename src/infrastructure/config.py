from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str


class BotSettings(BaseModel):
    token: str
    bot_name: str
    admin_id: int
    admin_username: str = "my7vpnadmin"


class PaymentSettings(BaseModel):
    payment_url: str
    payment_qr: str
    free_month: int


class AuthSettings(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 часа
    otp_expire_minutes: int = 5
    bot_token_expire_minutes: int = 10
    site_url: str = "http://localhost:8000"


class SmtpSettings(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""


class RemnawaveSettings(BaseModel):
    url: str = ""
    token: str = ""


class LoggingSettings(BaseModel):
    log_level: str = "INFO"
    log_json: bool = False
    log_to_file: bool = False
    log_dir: Path = Path("logs")
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5


class YuMoneySettings(BaseModel):
    wallet: str = ""                  # 15-значный номер кошелька
    notification_secret: str = ""     # секрет уведомлений из настроек кошелька
    success_url: str = ""             # URL редиректа после оплаты (необязательно)
    enabled: bool = False             # feature flag: False = старый ручной режим


class YooKassaSettings(BaseModel):
    shop_id: str = ""              # ID магазина из личного кабинета ЮKassa
    secret_key: str = ""           # Секретный ключ
    return_url: str = ""           # URL редиректа после оплаты
    enabled: bool = False          # feature flag


class AppConfig(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    remnawave: RemnawaveSettings = Field(default_factory=RemnawaveSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    yumoney: YuMoneySettings = Field(default_factory=YuMoneySettings)
    yookassa: YooKassaSettings = Field(default_factory=YooKassaSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


app_config = AppConfig()
