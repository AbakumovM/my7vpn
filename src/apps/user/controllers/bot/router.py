import structlog
from aiogram import F, Router, types
from aiogram.filters import Command
from dishka.integrations.aiogram import FromDishka

from src.apps.auth.application.interactor import AuthInteractor
from src.apps.auth.domain.commands import CreateBotToken
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import GetOrCreateUser, GetReferralCode
from src.apps.user.domain.exceptions import ReferralNotFound
from src.common.bot.keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_type_device,
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
                "❌ Вы уже использовали бесплатный месяц ранее",
                reply_markup=return_start(),
            )
            return

        # Нужен telegram_id реферера — берём через UserView через код
        # referral_id передаётся в callback для дальнейшего flow
        from src.apps.user.application.interfaces.gateway import UserGateway  # noqa: PLC0415

        gateway: UserGateway = interactor._gateway  # type: ignore[attr-defined]
        referrer = await gateway.get_by_referral_code(referral_code)
        referral_id = referrer.telegram_id if referrer else None

        await msg.answer(
            bot_repl.get_start_message_free_month(msg.from_user.full_name),
            reply_markup=get_keyboard_type_device(VpnAction.REFERRAL, referral_id),
        )
        return

    user = await interactor.get_or_create(GetOrCreateUser(telegram_id=msg.from_user.id))
    log.info("user_start")
    device_count = await user_view.get_device_count(msg.from_user.id)

    if device_count > 0:
        keyboard = create_inline_kb(
            1,
            CallbackAction.VPN_ERROR,
            CallbackAction.LIST_DEVICES,
            CallbackAction.SUPPORT_HELP,
        )
        await msg.answer(
            bot_repl.get_start(msg.from_user.full_name, device_count, user.balance),
            reply_markup=keyboard,
        )
    else:
        await msg.answer(
            bot_repl.get_start_message(msg.from_user.full_name),
            reply_markup=get_keyboard_type_device(VpnAction.NEW),
        )


@router.callback_query(F.data.in_([CallbackAction.CANCEL, CallbackAction.START]))
async def handle_start_callback(
    call: types.CallbackQuery,
    interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    try:
        user = await interactor.get_or_create(GetOrCreateUser(telegram_id=call.from_user.id))
        device_count = await user_view.get_device_count(call.from_user.id)
        keyboard = create_inline_kb(
            1,
            CallbackAction.VPN_ERROR,
            CallbackAction.LIST_DEVICES,
            CallbackAction.SUPPORT_HELP,
        )
        await call.message.answer(
            bot_repl.get_start(call.from_user.full_name, device_count, user.balance),
            reply_markup=keyboard,
        )
    except Exception:
        log.exception("handle_start_callback_error")
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
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


@router.message(Command(CallbackAction.INVITE))
async def handle_invite(
    msg: types.Message,
    interactor: FromDishka[UserInteractor],
) -> None:
    result = await interactor.get_referral_code(GetReferralCode(telegram_id=msg.from_user.id))
    keyboard = create_inline_kb(
        1,
        CallbackAction.VPN_ERROR,
        CallbackAction.LIST_DEVICES,
        CallbackAction.SUPPORT_HELP,
    )
    await msg.answer(
        bot_repl.get_message_invite_friend(result.referral_code),
        reply_markup=keyboard,
    )
