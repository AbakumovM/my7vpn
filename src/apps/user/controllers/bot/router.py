import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.auth.application.interactor import AuthInteractor
from src.apps.auth.domain.commands import CreateBotToken
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode
from src.apps.user.domain.exceptions import ReferralNotFound
from src.common.bot.keyboards.keyboards import (
    get_keyboard_device_count,
    get_keyboard_friends,
    get_keyboard_instruction_detail,
    get_keyboard_instruction_platforms,
    get_keyboard_main_menu,
    get_keyboard_subscription,
    return_start,
)
from src.common.bot.keyboards.user_actions import CallbackAction, VpnAction
from src.common.bot.lexicon.text_manager import bot_repl
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)
router = Router()


@router.message(Command(CallbackAction.START))
async def handle_start(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
    device_view: FromDishka[DeviceView],
) -> None:
    referral_code = msg.text.split(" ")[1] if len(msg.text.split(" ")) > 1 else None

    if referral_code:
        try:
            user = await interactor.get_or_create(
                GetOrCreateUser(telegram_id=msg.from_user.id, referred_by_code=referral_code)
            )
        except ReferralNotFound:
            await msg.answer(bot_repl.get_message_error_referral(), reply_markup=return_start())
            return

        if user.free_months:
            await msg.answer(
                "❌ Вы уже использовали бесплатный период ранее",
                reply_markup=return_start(),
            )
            return

        from src.apps.user.application.interfaces.gateway import UserGateway  # noqa: PLC0415

        gateway: UserGateway = interactor._gateway  # type: ignore[attr-defined]
        referrer = await gateway.get_by_referral_code(referral_code)
        referral_id = referrer.telegram_id if referrer else None

        # Реферальный flow — сразу к выбору количества устройств
        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_device_count(action=VpnAction.REFERRAL, referral_id=referral_id),
        )
        return

    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=msg.from_user.id))
    sub = await device_view.get_subscription_info(msg.from_user.id)

    if sub and sub.end_date:
        end_str = sub.end_date.strftime("%d.%m.%Y")
        await msg.answer(
            bot_repl.get_main_menu_active(
                msg.from_user.full_name, end_str, sub.device_limit, sub.device_limit, user.balance
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
    device_view: FromDishka[DeviceView],
) -> None:
    try:
        user = await interactor.get_or_create(GetOrCreateUser(telegram_id=call.from_user.id))
        sub = await device_view.get_subscription_info(call.from_user.id)

        if sub and sub.end_date:
            end_str = sub.end_date.strftime("%d.%m.%Y")
            await call.message.answer(
                bot_repl.get_main_menu_active(
                    call.from_user.full_name, end_str, sub.device_limit, sub.device_limit, user.balance
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

    from datetime import datetime, UTC  # noqa: PLC0415

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
    await call.message.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance),
        reply_markup=get_keyboard_friends(result.referral_code),
    )
    await call.answer()


@router.callback_query(F.data.startswith("copy_ref:"))
async def handle_copy_ref(call: types.CallbackQuery) -> None:
    referral_code = call.data.split(":", 1)[1]
    bot_name = app_config.bot.bot_name
    link = f"https://t.me/{bot_name}?start={referral_code}"
    await call.message.answer(f"🔗 Ваша реферальная ссылка:\n\n<code>{link}</code>")
    await call.answer()


@router.message(Command("invite"))
async def handle_invite(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=msg.from_user.id))
    stats = await user_view.get_referral_stats(msg.from_user.id)
    await msg.answer(
        bot_repl.get_friends_screen(stats.invited_count, stats.total_earned, stats.balance),
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
