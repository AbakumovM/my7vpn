from email.message import EmailMessage

import structlog
from aiosmtplib import SMTP

from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)


class SmtpService:
    def __init__(self) -> None:
        self._cfg = app_config.smtp

    async def send_otp(self, email: str, code: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._cfg.from_email
        msg["To"] = email
        msg["Subject"] = "Код для входа на сайт"
        msg.set_content(
            f"Ваш код для входа: {code}\n\n"
            f"Код действителен {app_config.auth.otp_expire_minutes} минут.\n"
            f"Если вы не запрашивали код — просто проигнорируйте это письмо."
        )

        try:
            smtp = SMTP(
                hostname=self._cfg.host,
                port=self._cfg.port,
                use_tls=False,
                start_tls=True,
            )
            await smtp.connect()
            await smtp.login(self._cfg.username, self._cfg.password)
            await smtp.send_message(msg)
            await smtp.quit()
            log.info("otp_email_sent", email=email)
        except Exception:
            log.exception("otp_email_send_failed", email=email)
            raise
