import uuid
import httpx
import structlog
from dataclasses import dataclass

from src.infrastructure.config import YooKassaSettings

log = structlog.get_logger(__name__)
YOOKASSA_API = "https://api.yookassa.ru/v3"


class YooKassaAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"YooKassa API error {status_code}: {detail}")


@dataclass(frozen=True)
class CreatedPayment:
    payment_id: str
    confirmation_url: str


class YooKassaClient:
    def __init__(self, settings: YooKassaSettings) -> None:
        self._auth = (settings.shop_id, settings.secret_key)
        self._return_url = settings.return_url

    async def create_payment(self, amount: int, pending_id: int) -> CreatedPayment:
        """Создаёт платёж в ЮKassa, возвращает payment_id и confirmation_url."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{YOOKASSA_API}/payments",
                auth=self._auth,
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={
                    "amount": {"value": f"{amount}.00", "currency": "RUB"},
                    "confirmation": {"type": "redirect", "return_url": self._return_url},
                    "description": f"VPN подписка #{pending_id}",
                    "metadata": {"pending_id": str(pending_id)},
                    "capture": True,
                },
            )
        if resp.status_code >= 400:
            raise YooKassaAPIError(resp.status_code, resp.text)
        data = resp.json()
        log.info("yookassa_payment_created", payment_id=data["id"], pending_id=pending_id)
        return CreatedPayment(
            payment_id=data["id"],
            confirmation_url=data["confirmation"]["confirmation_url"],
        )

    async def get_payment_status(self, payment_id: str) -> str:
        """Возвращает status платежа: pending / succeeded / canceled / etc."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{YOOKASSA_API}/payments/{payment_id}",
                auth=self._auth,
            )
        if resp.status_code >= 400:
            raise YooKassaAPIError(resp.status_code, resp.text)
        return resp.json()["status"]
