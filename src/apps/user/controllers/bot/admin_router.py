import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.user.application.interfaces.admin_view import AdminUserInfo, AdminView
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)

ADMIN_ID = app_config.bot.admin_id

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)


@router.message(Command("admin_stats"))
async def handle_admin_stats(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    stats = await admin_view.get_stats()
    await msg.answer(
        f"📊 <b>Статистика подписчиков</b>\n\n"
        f"👥 Всего пользователей: <b>{stats.total_users}</b>\n"
        f"✅ Активных подписок: <b>{stats.active_subscribers}</b>\n\n"
        f"📅 Новых сегодня: <b>{stats.new_today}</b>\n"
        f"📅 За неделю: <b>{stats.new_week}</b>\n"
        f"📅 За месяц: <b>{stats.new_month}</b>"
    )


@router.message(Command("admin_expiring"))
async def handle_admin_expiring(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    data = await admin_view.get_expiring()
    await msg.answer(
        f"⏳ <b>Истекающие подписки</b>\n\n"
        f"За 3 дня: <b>{data.expiring_3d}</b>\n"
        f"За 7 дней: <b>{data.expiring_7d}</b>\n"
        f"За 30 дней: <b>{data.expiring_30d}</b>"
    )


@router.message(Command("admin_churn"))
async def handle_admin_churn(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    data = await admin_view.get_churn()
    await msg.answer(
        f"📉 <b>Отток подписчиков</b>\n\n"
        f"❌ Не продлили за 7 дней: <b>{data.churned_7d}</b>\n"
        f"❌ Не продлили за 30 дней: <b>{data.churned_30d}</b>\n\n"
        f"📊 Renewal rate (30д): <b>{data.renewal_rate_30d}%</b>"
    )


@router.message(Command("admin_user"))
async def handle_admin_user(
    msg: types.Message,
    admin_view: FromDishka[AdminView],
) -> None:
    args = msg.text.split() if msg.text else []
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await msg.answer("Использование: /admin_user <telegram_id>")
        return

    telegram_id = int(args[1])
    info: AdminUserInfo | None = await admin_view.get_user_info(telegram_id)

    if info is None:
        await msg.answer(f"❌ Пользователь {telegram_id} не найден.")
        return

    if info.active_until:
        end_str = info.active_until.strftime("%d.%m.%Y")
        sub_line = f"📅 Подписка до: <b>{end_str}</b>"
        if info.device_limit is not None:
            sub_line += f"\n📱 Девайсов: <b>{info.device_limit}</b>"
    else:
        sub_line = "📅 Подписка: <b>нет активной</b>"

    referrer_line = (
        f"🔗 Реферал от: <b>{info.referred_by}</b>"
        if info.referred_by
        else "🔗 Реферал: нет"
    )

    await msg.answer(
        f"👤 <b>Пользователь {info.telegram_id}</b>\n\n"
        f"{sub_line}\n"
        f"💰 Баланс: <b>{info.balance} руб.</b>\n"
        f"{referrer_line}"
    )
