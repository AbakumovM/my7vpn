import re

import structlog
from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from dishka.integrations.aiogram import FromDishka

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.application.interfaces.view import DeviceView
from src.apps.device.domain.commands import (
    CreateDevice,
    CreateDeviceFree,
    DeleteDevice,
    RenewSubscription,
)
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import (
    AddReferralBonus,
    DeductUserBalance,
    MarkFreeMonthUsed,
    SetUserEmail,
)
from src.common.bot.cbdata import VpnCallback
from src.common.bot.files import get_photo_for_pay
from src.common.bot.keyboards.keyboards import (
    create_inline_kb,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_devices,
    get_keyboard_devices_for_del,
    get_keyboard_for_details_device,
    get_keyboard_skip_email,
    get_keyboard_start,
    get_keyboard_tariff,
    get_keyboard_type_device,
    get_keyboard_yes_or_no_for_update,
    return_start,
)
from src.common.bot.keyboards.user_actions import (
    CallbackAction,
    ChoiceType,
    PaymentStatus,
    VpnAction,
)
from src.common.bot.lexicon.text_manager import bot_repl
from src.common.bot.states import EmailInput
from src.infrastructure.config import app_config

log = structlog.get_logger(__name__)
router = Router()

ADMIN_ID = app_config.bot.admin_id
LINK = app_config.payment.payment_url


from aiogram.filters import Command as _Command  # noqa: E402


@router.message(_Command("devices"))
async def handle_devices_cmd(
    msg: types.Message,
    device_view: FromDishka[DeviceView],
) -> None:
    devices = await device_view.list_for_user(msg.from_user.id)
    if devices:
        await msg.answer(
            text=bot_repl.get_message_devices(len(devices)),
            reply_markup=get_keyboard_devices(devices, "conf"),
        )
    else:
        await msg.answer("У вас нет активных устройств", reply_markup=get_keyboard_start())


@router.callback_query(F.data == CallbackAction.LIST_DEVICES)
async def handle_list_devices(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    try:
        devices = await device_view.list_for_user(call.from_user.id)
        if devices:
            await call.message.answer(
                text=bot_repl.get_message_devices(len(devices)),
                reply_markup=get_keyboard_devices(devices, "conf"),
            )
        else:
            await call.message.answer("У вас нет активных устройств")
    except Exception:
        log.exception("handle_list_devices_error")
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("del"))
async def handle_delete_prompt(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    try:
        devices = await device_view.list_for_user(call.from_user.id)
        if not devices:
            await call.message.answer("У вас нет активных устройств")
            return
        await call.message.answer(
            "Какое устройство вы хотите отключить?",
            reply_markup=get_keyboard_devices_for_del(devices),
        )
    except Exception:
        log.exception("handle_delete_prompt_error")
        await call.message.answer(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("appr_del_device"))
async def handle_delete_confirm(
    call: types.CallbackQuery,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    device_id = int(call.data.split(":")[1])
    try:
        device_name = await interactor.delete_device(DeleteDevice(device_id=device_id))
        log.info("device_deleted", device_id=device_id, device_name=device_name)
        await call.message.edit_text("Устройство удалено")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"❌ Пользователь удалил у себя VPN!\n"
                f"👤 Имя: {call.from_user.username}\n"
                f"🆔 ID: {call.from_user.id}\n"
                f"📋 Девайс: {device_name}"
            ),
        )
    except Exception:
        log.exception("handle_delete_confirm_error", device_id=device_id)
        await call.message.edit_text(
            "Что то пошло не так. Попробуй позже или напиши в поддержку @my7vpnadmin."
        )


@router.callback_query(F.data.startswith("conf"))
async def handle_device_detail(
    call: types.CallbackQuery,
    device_view: FromDishka[DeviceView],
) -> None:
    device_id = int(call.data.split(":")[1])
    result = await device_view.get_full_info(device_id)
    if result is None:
        await call.message.answer("Устройство не найдено")
        return
    text, device_name = bot_repl.generate_device_info_message(
        {
            "device_name": result.device_name,
            "end_date": result.end_date,
            "amount": result.amount,
            "payment_date": result.payment_date,
        }
    )
    await call.message.answer(
        text=text,
        reply_markup=get_keyboard_for_details_device(device_name=result.device_name),
    )


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


async def _show_qr_payment(
    call: types.CallbackQuery,
    action: str,
    device: str,
    duration: int,
    referral_id: int | None,
    payment: int,
    balance: int,
) -> None:
    """Показать QR-код для оплаты (Step 5)."""
    file_data = await get_photo_for_pay()
    await call.message.answer_photo(
        photo=file_data,
        caption=bot_repl.get_approve_payment(amount=payment, payment_link=LINK),
        reply_markup=get_keyboard_approve_payment_or_cancel(
            action=action,
            device=device,
            duration=duration,
            referral_id=referral_id,
            payment=payment,
            balance=balance,
            choice=ChoiceType.STOP,
        ),
    )


async def _show_qr_from_state(
    msg_or_call: types.Message | types.CallbackQuery,
    state: FSMContext,
) -> None:
    """Восстановить данные из FSM state и показать QR."""
    data = await state.get_data()
    await state.clear()

    message = msg_or_call.message if isinstance(msg_or_call, types.CallbackQuery) else msg_or_call

    file_data = await get_photo_for_pay()
    await message.answer_photo(
        photo=file_data,
        caption=bot_repl.get_approve_payment(amount=data["payment"], payment_link=LINK),
        reply_markup=get_keyboard_approve_payment_or_cancel(
            action=data["action"],
            device=data["device"],
            duration=data["duration"],
            referral_id=data.get("referral_id"),
            payment=data["payment"],
            balance=data["balance"],
            choice=ChoiceType.STOP,
        ),
    )


@router.message(EmailInput.waiting_for_email)
async def handle_email_input(
    msg: types.Message,
    state: FSMContext,
    user_interactor: FromDishka[UserInteractor],
) -> None:
    """Обработка ввода email пользователем."""
    email = msg.text.strip().lower() if msg.text else ""
    if not EMAIL_RE.match(email):
        await msg.answer(
            "Неверный формат email. Попробуйте ещё раз или нажмите «Пропустить».",
            reply_markup=get_keyboard_skip_email(),
        )
        return

    await user_interactor.set_email(SetUserEmail(telegram_id=msg.from_user.id, email=email))
    await msg.answer(f"Email {email} сохранён.")
    await _show_qr_from_state(msg, state)


@router.callback_query(F.data == "skip_email", EmailInput.waiting_for_email)
async def handle_skip_email(
    call: types.CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь пропустил ввод email."""
    await call.message.edit_text("Хорошо, вы можете указать email позже.")
    await _show_qr_from_state(call, state)
    await call.answer()


@router.callback_query(VpnCallback.filter())
async def handle_vpn_flow(
    call: types.CallbackQuery,
    callback_data: VpnCallback,
    bot: Bot,
    state: FSMContext,
    interactor: FromDishka[DeviceInteractor],
    user_interactor: FromDishka[UserInteractor],
    user_view: FromDishka[UserView],
) -> None:
    action = callback_data.action
    device = callback_data.device
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice
    payment_status = callback_data.payment_status

    # Шаг 1: выбор типа устройства
    if device is None:
        await call.message.edit_text(
            bot_repl.get_message_for_added_device(),
            reply_markup=get_keyboard_type_device(action=action, referral_id=referral_id),
        )
        await call.answer()
        return

    # Шаг 2: выбор тарифа
    if duration == 0:
        await call.message.edit_text(
            "Выберете тариф, который хотите подключить:",
            reply_markup=get_keyboard_tariff(action=action, device=device, referral_id=referral_id),
        )
        await call.answer()
        return

    # Шаг 3: показ суммы к оплате
    if balance is None:
        user_balance = await user_view.get_balance(call.from_user.id)
        finally_payment = max(payment - user_balance, 0)
        new_balance = max(user_balance - payment, 0)
        await call.message.edit_text(
            bot_repl.get_full_info_payment(device, duration, finally_payment, payment),
            reply_markup=get_keyboard_yes_or_no_for_update(
                action=action,
                device=device,
                duration=duration,
                balance=new_balance,
                payment=finally_payment,
                referral_id=referral_id,
            ),
        )
        await call.answer()
        return

    # Шаг 4: отмена
    if choice == ChoiceType.NO or payment_status == PaymentStatus.FAILED:
        keyboard = create_inline_kb(1, CallbackAction.START)
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.send_messages_cancel_choice(), reply_markup=keyboard
        )
        await call.answer()
        return

    # Шаг 5: подтверждение → проверка email → показ QR-оплаты
    if choice == ChoiceType.YES:
        await call.message.delete()

        # Проверяем наличие email у пользователя
        user_email = await user_view.get_email(call.from_user.id)
        if user_email is None:
            # Сохраняем данные flow в FSM state
            await state.set_data(
                {
                    "action": action,
                    "device": device,
                    "duration": duration,
                    "referral_id": referral_id,
                    "payment": payment,
                    "balance": balance,
                }
            )
            await state.set_state(EmailInput.waiting_for_email)
            await call.message.answer(
                "📧 Укажите вашу электронную почту — она понадобится "
                "для входа на сайт и получения чеков.",
                reply_markup=get_keyboard_skip_email(),
            )
            await call.answer()
            return

        await _show_qr_payment(
            call,
            action,
            device,
            duration,
            referral_id,
            payment,
            balance,
        )
        await call.answer()
        return

    # Шаг 6a: новая подписка — оплата успешна
    if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
        result = await interactor.create_device(
            CreateDevice(
                telegram_id=call.from_user.id,
                device_type=device,
                period_months=duration,
                amount=payment,
            )
        )
        log.info(
            "device_created",
            device_name=result.device_name,
            device_type=device,
            period_months=duration,
            amount=payment,
        )
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.get_message_success_payment(), reply_markup=return_start()
        )
        if balance > 0:
            await user_interactor.deduct_balance(
                DeductUserBalance(telegram_id=call.from_user.id, amount=balance)
            )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_message_admin_new_device(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=result.device_name,
                duration=duration,
                payment=payment,
            ),
        )
        await call.answer()
        return

    # Шаг 6b: продление подписки
    if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
        result_renew = await interactor.renew_subscription(
            RenewSubscription(
                device_name=callback_data.device_name or device,
                period_months=duration,
                amount=payment,
            )
        )
        log.info(
            "subscription_renewed",
            device_name=result_renew.device_name,
            period_months=duration,
            amount=payment,
        )
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.get_message_success_payment_update(), reply_markup=return_start()
        )
        if balance > 0:
            await user_interactor.deduct_balance(
                DeductUserBalance(telegram_id=call.from_user.id, amount=balance)
            )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_messages_for_admin_update(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=device,
                duration=duration,
                payment=payment,
            ),
        )
        await call.answer()
        return

    # Шаг 6c: реферальный бесплатный период
    if action == VpnAction.REFERRAL:
        result_free = await interactor.create_device_free(
            CreateDeviceFree(
                telegram_id=call.from_user.id,
                device_type=device,
                period_days=app_config.payment.free_month,
            )
        )
        log.info(
            "device_created_free",
            device_name=result_free.device_name,
            device_type=device,
            referral_id=referral_id,
        )
        await user_interactor.mark_free_month_used(MarkFreeMonthUsed(telegram_id=call.from_user.id))
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=bot_repl.send_message_admin_new_user_referral(
                username=call.from_user.username,
                user_id=call.from_user.id,
                device=result_free.device_name,
                referral_id=referral_id,
            ),
        )
        await call.message.edit_text(
            bot_repl.get_message_success_free_month(device), reply_markup=return_start()
        )
        if referral_id:
            await user_interactor.add_referral_bonus(
                AddReferralBonus(referrer_telegram_id=referral_id, amount=50)
            )
            log.info("referral_bonus_added", referrer_id=referral_id, amount=50)
            await bot.send_message(
                chat_id=referral_id, text=bot_repl.get_message_new_user_referral()
            )
        await call.answer()
