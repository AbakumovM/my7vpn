import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.auth.application.interactor import AuthInteractor
from src.apps.auth.domain.commands import CreateBotToken
from src.apps.device.application.interfaces.remnawave_gateway import RemnawaveGateway
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode
from src.common.bot.keyboards.keyboards import (
    get_keyboard_confirm_delete_all,
    get_keyboard_friends,
    get_keyboard_hwid_devices,
    get_keyboard_instruction_platforms,
    get_keyboard_main_menu,
    get_keyboard_referral_activate,
    get_keyboard_subscription,
    return_start,
)
from src.common.bot.keyboards.user_actions import CallbackAction
from src.common.bot.lexicon.text_manager import bot_repl
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)
router = Router()


async def _get_hwid_used(remnawave_uuid: str | None, remnawave_gateway: RemnawaveGateway) -> int:
    """Возвращает количество подключённых HWID-устройств. При ошибке — 0."""
    if remnawave_uuid is None:
        return 0
    try:
        return await remnawave_gateway.get_hwid_devices_count(remnawave_uuid)
    except Exception:
        log.warning("hwid_count_fetch_failed", uuid=remnawave_uuid)
        return 0


@router.message(Command(CallbackAction.START))
async def handle_start(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
    device_view: FromDishka[DeviceView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    referral_code = msg.text.split(" ")[1] if msg.text and len(msg.text.split(" ")) > 1 else None

    if referral_code:
        # 1. Код существует → получаем telegram_id реферера
        referral_id = await user_view.get_referrer_telegram_id(referral_code)
        if referral_id is None:
            await msg.answer(bot_repl.get_message_error_referral(), reply_markup=return_start())
            return

        # 2. Нельзя использовать свою ссылку
        if referral_id == msg.from_user.id:
            await msg.answer(
                "❌ Нельзя использовать собственную реферальную ссылку.",
                reply_markup=return_start(),
            )
            return

        # 3. Только новые пользователи
        existing_user_id = await user_view.get_user_id(msg.from_user.id)
        if existing_user_id is not None:
            await msg.answer(
                "ℹ️ Эта реферальная ссылка предназначена для новых пользователей.",
                reply_markup=return_start(),
            )
            return

        # Создаём пользователя с привязкой к рефереру
        await interactor.get_or_create(
            GetOrCreateUser(telegram_id=msg.from_user.id, referred_by_code=referral_code)
        )

        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_referral_activate(referral_id=referral_id),
        )
        return

    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=msg.from_user.id))
    sub = await device_view.get_subscription_info(msg.from_user.id)

    if sub and sub.end_date:
        end_str = sub.end_date.strftime("%d.%m.%Y")
        remnawave_uuid = await user_view.get_remnawave_uuid(msg.from_user.id)
        used = await _get_hwid_used(remnawave_uuid, remnawave_gateway)
        await msg.answer(
            bot_repl.get_main_menu_active(
                msg.from_user.full_name, end_str, used, sub.device_limit, user.balance
            ),
            reply_markup=get_keyboard_main_menu(has_subscription=True),
        )
    else:
        await msg.answer(
            bot_repl.get_main_menu_new(msg.from_user.full_name),
            reply_markup=get_keyboard_main_menu(has_subscription=False),
        )


@router.callback_query(F.data.in_([CallbackAction.CANCEL, CallbackAction.START]))
async def handle_start_callback(
    call: types.CallbackQuery,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
    device_view: FromDishka[DeviceView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    await call.answer()
    try:
        user = await interactor.get_or_create(GetOrCreateUser(telegram_id=call.from_user.id))
        sub = await device_view.get_subscription_info(call.from_user.id)

        if sub and sub.end_date:
            end_str = sub.end_date.strftime("%d.%m.%Y")
            remnawave_uuid = await user_view.get_remnawave_uuid(call.from_user.id)
            used = await _get_hwid_used(remnawave_uuid, remnawave_gateway)
            await call.message.answer(
                bot_repl.get_main_menu_active(
                    call.from_user.full_name, end_str, used, sub.device_limit, user.balance
                ),
                reply_markup=get_keyboard_main_menu(has_subscription=True),
            )
        else:
            await call.message.answer(
                bot_repl.get_main_menu_new(call.from_user.full_name),
                reply_markup=get_keyboard_main_menu(has_subscription=False),
            )
    except Exception:
        log.exception("handle_start_callback_error")
        await call.message.answer(
            "Что-то пошло не так. Попробуйте позже или напишите в поддержку.",
        )


@router.callback_query(F.data == CallbackAction.MY_SUBSCRIPTION)
async def handle_my_subscription(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    sub = await device_view.get_subscription_info(call.from_user.id)
    if sub is None or sub.end_date is None:
        await call.message.answer(
            bot_repl.get_no_subscription(),
            reply_markup=get_keyboard_main_menu(has_subscription=False),
        )
        await call.answer()
        return

    from datetime import UTC, datetime  # noqa: PLC0415

    days_left = (sub.end_date - datetime.now(UTC)).days
    end_str = sub.end_date.strftime("%d.%m.%Y")

    await call.message.answer(
        bot_repl.get_subscription_info(
            end_date=end_str,
            device_limit=sub.device_limit,
            last_payment=sub.last_payment_amount,
            subscription_url=sub.subscription_url,
            days_left=days_left,
        ),
        reply_markup=get_keyboard_subscription(is_expiring=days_left <= 7),
    )
    await call.answer()


@router.callback_query(F.data == CallbackAction.INSTRUCTION)
async def handle_instruction(call: types.CallbackQuery) -> None:
    await call.message.answer(
        "📖 <b>Инструкция по подключению</b>\n\nВыберите вашу платформу:",
        reply_markup=get_keyboard_instruction_platforms(),
    )
    await call.answer()


@router.callback_query(F.data == CallbackAction.FRIENDS)
async def handle_friends(
    call: types.CallbackQuery,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=call.from_user.id))
    stats = await user_view.get_referral_stats(call.from_user.id)
    bot_name = app_config.bot.bot_name
    referral_link = f"https://t.me/{bot_name}?start={result.referral_code}"
    await call.message.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance, referral_link),
        reply_markup=get_keyboard_friends(result.referral_code),
    )
    await call.answer()



@router.message(Command("invite"))
async def handle_invite(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=msg.from_user.id))
    stats = await user_view.get_referral_stats(msg.from_user.id)
    bot_name = app_config.bot.bot_name
    referral_link = f"https://t.me/{bot_name}?start={result.referral_code}"
    await msg.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance, referral_link),
        reply_markup=get_keyboard_friends(result.referral_code),
    )


@router.message(Command("web"))
async def handle_web_login(
    msg: types.Message,
    user_view: FromDishka[UserView],
    auth_interactor: FromDishka[AuthInteractor],
) -> None:
    user_id = await user_view.get_user_id(msg.from_user.id)
    if user_id is None:
        await msg.answer("Сначала запустите бота командой /start")
        return

    token = await auth_interactor.create_bot_token(CreateBotToken(user_id=user_id))
    site_url = app_config.auth.site_url
    link = f"{site_url}/api/v1/auth/bot-token/{token}"
    await msg.answer(
        f"🌐 Ваша ссылка для входа на сайт:\n{link}\n\n"
        f"Ссылка действительна {app_config.auth.bot_token_expire_minutes} минут.",
    )


@router.callback_query(F.data == CallbackAction.CABINET)
async def handle_cabinet(
    call: types.CallbackQuery,
) -> None:
    await call.answer()
    await call.message.answer(
        "🚧 <b>Личный кабинет</b>\n\n"
        "Функционал находится в разработке. Скоро будет доступен!"
    )


async def _get_hwid_device_dicts(
    telegram_id: int,
    user_view: UserView,
    remnawave_gateway: RemnawaveGateway,
) -> list[dict] | None:
    """Возвращает список устройств как dict, или None если нет uuid."""
    remnawave_uuid = await user_view.get_remnawave_uuid(telegram_id)
    if remnawave_uuid is None:
        return None
    try:
        devices = await remnawave_gateway.get_hwid_devices(remnawave_uuid)
    except Exception:
        log.warning("hwid_devices_fetch_failed", telegram_id=telegram_id)
        return []
    return [
        {
            "hwid": d.hwid,
            "platform": d.platform,
            "os_version": d.os_version,
            "device_model": d.device_model,
        }
        for d in devices
    ]


@router.callback_query(F.data == CallbackAction.HWID_DEVICES)
async def handle_hwid_devices(
    call: types.CallbackQuery,
    user_view: FromDishka[UserView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    devices = await _get_hwid_device_dicts(call.from_user.id, user_view, remnawave_gateway)
    if devices is None:
        await call.message.answer("У вас нет активной подписки.")
        await call.answer()
        return
    await call.message.answer(
        bot_repl.get_hwid_devices_screen(devices),
        reply_markup=get_keyboard_hwid_devices(devices),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hwid_del:"))
async def handle_hwid_delete_one(
    call: types.CallbackQuery,
    user_view: FromDishka[UserView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    hwid = call.data.split(":", 1)[1]
    remnawave_uuid = await user_view.get_remnawave_uuid(call.from_user.id)
    if remnawave_uuid is None:
        await call.answer("Подписка не найдена", show_alert=True)
        return
    try:
        await remnawave_gateway.delete_hwid_device(remnawave_uuid, hwid)
    except Exception:
        log.warning("hwid_delete_failed", uuid=remnawave_uuid, hwid=hwid)
        await call.answer("Ошибка при удалении. Попробуйте позже.", show_alert=True)
        return

    # Обновляем список
    devices = await _get_hwid_device_dicts(call.from_user.id, user_view, remnawave_gateway)
    await call.message.edit_text(
        bot_repl.get_hwid_devices_screen(devices or []),
        reply_markup=get_keyboard_hwid_devices(devices or []),
    )
    await call.answer("Устройство удалено")


@router.callback_query(F.data == CallbackAction.HWID_DELETE_ALL)
async def handle_hwid_delete_all_prompt(call: types.CallbackQuery) -> None:
    await call.message.answer(
        bot_repl.get_hwid_delete_all_confirm(),
        reply_markup=get_keyboard_confirm_delete_all(),
    )
    await call.answer()


@router.callback_query(F.data == CallbackAction.HWID_DELETE_ALL_CONFIRM)
async def handle_hwid_delete_all_confirm(
    call: types.CallbackQuery,
    user_view: FromDishka[UserView],
    remnawave_gateway: FromDishka[RemnawaveGateway],
) -> None:
    remnawave_uuid = await user_view.get_remnawave_uuid(call.from_user.id)
    if remnawave_uuid is None:
        await call.answer("Подписка не найдена", show_alert=True)
        return
    try:
        await remnawave_gateway.delete_all_hwid_devices(remnawave_uuid)
    except Exception:
        log.warning("hwid_delete_all_failed", uuid=remnawave_uuid)
        await call.answer("Ошибка при удалении. Попробуйте позже.", show_alert=True)
        return
    await call.message.edit_text(
        "✅ Все устройства удалены.\n\n"
        "При следующем подключении к VPN устройство зарегистрируется заново.",
        reply_markup=get_keyboard_hwid_devices([]),
    )
    await call.answer()
