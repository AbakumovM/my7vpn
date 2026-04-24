import re

import structlog
from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from dishka.integrations.aiogram import FromDishka

from src.apps.device.application.interactor import DeviceInteractor
from src.apps.device.domain.commands import (
    ConfirmPayment,
    CreateDevice,
    CreateDeviceFree,
    CreatePendingPayment,
    RejectPayment,
    RenewSubscription,
)
from src.apps.device.domain.exceptions import PendingPaymentNotFound
from src.apps.user.application.interactor import UserInteractor
from src.apps.user.application.interfaces.view import UserView
from src.apps.user.domain.commands import (
    AddReferralBonus,
    MarkFreeMonthUsed,
    SetUserEmail,
)
from src.common.bot.cbdata import AdminConfirmCallback, VpnCallback
from src.common.bot.files import get_photo_for_pay
from src.common.bot.keyboards.keyboards import (
    get_keyboard_admin_confirm,
    get_keyboard_approve_payment_or_cancel,
    get_keyboard_confirm_payment,
    get_keyboard_device_count,
    get_keyboard_main_menu,
    get_keyboard_payment_link,
    get_keyboard_skip_email,
    get_keyboard_tariff,
    get_keyboard_vpn_received,
    return_start,
)
from src.infrastructure.yookassa.client import YooKassaClient
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


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


async def _show_qr_payment(
    call: types.CallbackQuery,
    action: str,
    device: str,
    device_limit: int,
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
            device_limit=device_limit,
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
            device="vpn",
            device_limit=data.get("device_limit", 1),
            duration=data["duration"],
            referral_id=data.get("referral_id"),
            payment=data["payment"],
            balance=data["balance"],
            choice=ChoiceType.STOP,
        ),
    )


async def _show_payment_link(
    msg_or_call: types.Message | types.CallbackQuery,
    interactor: DeviceInteractor,
    action: str,
    device: str,
    device_limit: int,
    duration: int,
    amount: int,
    balance: int,
    device_name: str | None,
    user_telegram_id: int,
) -> None:
    """Создать pending, получить ссылку ЮKassa и отправить пользователю."""
    pending = await interactor.create_pending_payment(
        CreatePendingPayment(
            user_telegram_id=user_telegram_id,
            action=action,
            device_type=device,
            duration=duration,
            amount=amount,
            balance_to_deduct=balance,
            device_limit=device_limit,
            device_name=device_name,
        )
    )
    yookassa_client = YooKassaClient(app_config.yookassa)
    created = await yookassa_client.create_payment(amount=amount, pending_id=pending.id)

    message = msg_or_call.message if isinstance(msg_or_call, types.CallbackQuery) else msg_or_call
    await message.answer(
        bot_repl.get_approve_payment_link(amount=amount, confirmation_url=created.confirmation_url),
        reply_markup=get_keyboard_payment_link(),
    )


@router.message(EmailInput.waiting_for_email)
async def handle_email_input(
    msg: types.Message,
    state: FSMContext,
    user_interactor: FromDishka[UserInteractor],
    interactor: FromDishka[DeviceInteractor],
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

    if app_config.yookassa.enabled:
        data = await state.get_data()
        await state.clear()
        await _show_payment_link(
            msg, interactor,
            action=data["action"],
            device="vpn",
            device_limit=data.get("device_limit", 1),
            duration=data["duration"],
            amount=data["payment"],
            balance=data["balance"],
            device_name=None,
            user_telegram_id=msg.from_user.id,
        )
    else:
        await _show_qr_from_state(msg, state)


@router.callback_query(F.data == "skip_email", EmailInput.waiting_for_email)
async def handle_skip_email(
    call: types.CallbackQuery,
    state: FSMContext,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    """Пользователь пропустил ввод email."""
    await call.message.edit_text("Хорошо, вы можете указать email позже.")

    if app_config.yookassa.enabled:
        data = await state.get_data()
        await state.clear()
        await _show_payment_link(
            call, interactor,
            action=data["action"],
            device="vpn",
            device_limit=data.get("device_limit", 1),
            duration=data["duration"],
            amount=data["payment"],
            balance=data["balance"],
            device_name=None,
            user_telegram_id=call.from_user.id,
        )
    else:
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
    device_limit = callback_data.device_limit
    duration = callback_data.duration
    referral_id = callback_data.referral_id
    payment = callback_data.payment
    balance = callback_data.balance
    choice = callback_data.choice
    payment_status = callback_data.payment_status

    # Шаг 1: выбор количества устройств
    if device_limit is None:
        await call.message.edit_text(
            bot_repl.get_choose_device_count(),
            reply_markup=get_keyboard_device_count(action=action, referral_id=referral_id),
        )
        await call.answer()
        return

    # Шаг 2: выбор тарифа
    if duration == 0:
        await call.message.edit_text(
            bot_repl.get_choose_tariff(device_limit),
            reply_markup=get_keyboard_tariff(
                action=action, device_limit=device_limit, referral_id=referral_id
            ),
        )
        await call.answer()
        return

    # Шаг 3: подтверждение оплаты
    if balance is None:
        user_balance = await user_view.get_balance(call.from_user.id)
        finally_payment = max(payment - user_balance, 0)
        balance_to_deduct = min(user_balance, payment)
        bonus = payment - finally_payment
        await call.message.edit_text(
            bot_repl.get_confirm_payment(
                device_limit=device_limit,
                duration=duration,
                price=payment,
                bonus=bonus,
                total=finally_payment,
            ),
            reply_markup=get_keyboard_confirm_payment(
                action=action,
                device_limit=device_limit,
                duration=duration,
                balance=balance_to_deduct,
                payment=finally_payment,
                referral_id=referral_id,
            ),
        )
        await call.answer()
        return

    # Шаг 4: отмена
    if choice == ChoiceType.NO or payment_status == PaymentStatus.FAILED:
        await call.message.delete()
        await call.message.answer(
            text=bot_repl.send_messages_cancel_choice(),
            reply_markup=return_start(),
        )
        await call.answer()
        return

    # Шаг 5: подтверждение → проверка email → показ оплаты
    if choice == ChoiceType.YES:
        await call.message.delete()

        # Проверяем наличие email у пользователя
        user_email = await user_view.get_email(call.from_user.id)
        if user_email is None:
            await state.set_data({
                "action": action,
                "device_limit": device_limit,
                "duration": duration,
                "referral_id": referral_id,
                "payment": payment,
                "balance": balance,
            })
            await state.set_state(EmailInput.waiting_for_email)
            await call.message.answer(
                "📧 Укажите вашу электронную почту — она понадобится "
                "для входа на сайт и получения чеков.",
                reply_markup=get_keyboard_skip_email(),
            )
            await call.answer()
            return

        if app_config.yookassa.enabled:
            await _show_payment_link(
                call, interactor,
                action=action,
                device="vpn",
                device_limit=device_limit or 1,
                duration=duration,
                amount=payment,
                balance=balance,
                device_name=None,
                user_telegram_id=call.from_user.id,
            )
            await call.answer()
            return

        await _show_qr_payment(
            call, action, "vpn", device_limit or 1, duration, referral_id, payment, balance,
        )
        await call.answer()
        return

    # Шаг 6a: новая подписка — оплата заявлена, ждём подтверждения админа
    if action == CallbackAction.NEW_SUB and payment_status == PaymentStatus.SUCCESS:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="new",
                device_type="vpn",
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
            )
        )
        await call.message.delete()
        await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💳 Новый платёж!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"📱 Устройств: {device_limit}\n"
                f"📅 Срок: {duration} мес → {payment}₽"
            ),
            reply_markup=get_keyboard_admin_confirm(pending.id),
        )
        log.info(
            "pending_payment_created",
            pending_id=pending.id,
            user_id=call.from_user.id,
            device_type="vpn",
            duration=duration,
            amount=payment,
        )
        return

    # Шаг 6b: продление — ждём подтверждения админа
    if action == VpnAction.RENEW and payment_status == PaymentStatus.SUCCESS:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        pending = await interactor.create_pending_payment(
            CreatePendingPayment(
                user_telegram_id=call.from_user.id,
                action="renew",
                device_type="vpn",
                duration=duration,
                amount=payment,
                balance_to_deduct=balance,
                device_limit=device_limit or 1,
            )
        )
        await call.message.delete()
        await call.message.answer("⏳ Ожидайте подтверждения оплаты администратором")
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔄 Продление подписки!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"📱 Устройств: {device_limit}\n"
                f"📅 Срок: {duration} мес → {payment}₽"
            ),
            reply_markup=get_keyboard_admin_confirm(pending.id),
        )
        log.info(
            "pending_renewal_created",
            pending_id=pending.id,
            user_id=call.from_user.id,
            duration=duration,
            amount=payment,
        )
        return

    # Шаг 6c: реферальный бесплатный период
    if action == VpnAction.REFERRAL:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            await call.answer()
            return
        await call.answer()
        result_free = await interactor.create_device_free(
            CreateDeviceFree(
                telegram_id=call.from_user.id,
                device_type="vpn",
                period_days=app_config.payment.free_month,
            )
        )
        log.info(
            "device_created_free",
            device_name=result_free.device_name,
            device_type="vpn",
            referral_id=referral_id,
        )
        await user_interactor.mark_free_month_used(MarkFreeMonthUsed(telegram_id=call.from_user.id))
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎁 Реферальная подписка!\n"
                f"👤 @{call.from_user.username} (id: {call.from_user.id})\n"
                f"🆔 Пригласил: {referral_id}"
            ),
        )
        await call.message.answer(
            bot_repl.get_message_success_free_month("VPN"),
            reply_markup=return_start(),
        )
        if referral_id:
            await user_interactor.add_referral_bonus(
                AddReferralBonus(referrer_telegram_id=referral_id, amount=50)
            )
            log.info("referral_bonus_added", referrer_id=referral_id, amount=50)
            await bot.send_message(
                chat_id=referral_id, text=bot_repl.get_message_new_user_referral()
            )


@router.callback_query(AdminConfirmCallback.filter(F.action == "confirm"), F.from_user.id == ADMIN_ID)
async def handle_admin_confirm(
    call: types.CallbackQuery,
    callback_data: AdminConfirmCallback,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    try:
        result = await interactor.confirm_payment(ConfirmPayment(pending_id=callback_data.pending_id))
    except PendingPaymentNotFound:
        await call.message.edit_text("⚠️ Платёж не найден — возможно, уже обработан")
        await call.answer()
        return
    except Exception:
        log.exception("admin_confirm_error", pending_id=callback_data.pending_id)
        await call.message.edit_text("❌ Ошибка при подтверждении. Проверьте логи.")
        await call.answer()
        return

    if result.subscription_url:
        if result.action == "new":
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text="✅ Оплата подтверждена! Ваша ссылка для подключения 👇",
            )
        else:
            end_str = result.end_date.strftime("%d.%m.%Y") if result.end_date else "—"
            await bot.send_message(
                chat_id=result.user_telegram_id,
                text=f"✅ Подписка продлена до {end_str}. Ваша ссылка для подключения 👇",
            )
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"`{result.subscription_url}`",
            parse_mode="Markdown",
            reply_markup=get_keyboard_vpn_received(),
        )
    else:
        end_str = result.end_date.strftime("%d.%m.%Y") if result.end_date else "—"
        await bot.send_message(
            chat_id=result.user_telegram_id,
            text=f"✅ Оплата подтверждена! Подписка активна до {end_str}.",
            reply_markup=return_start(),
        )

    await call.message.edit_text(f"✅ Выдано: {result.device_name}")
    await call.answer("Готово!")
    log.info(
        "payment_confirmed",
        pending_id=callback_data.pending_id,
        device_name=result.device_name,
        action=result.action,
    )


@router.callback_query(AdminConfirmCallback.filter(F.action == "reject"), F.from_user.id == ADMIN_ID)
async def handle_admin_reject(
    call: types.CallbackQuery,
    callback_data: AdminConfirmCallback,
    bot: Bot,
    interactor: FromDishka[DeviceInteractor],
) -> None:
    try:
        result = await interactor.reject_payment(RejectPayment(pending_id=callback_data.pending_id))
    except PendingPaymentNotFound:
        await call.message.edit_text("⚠️ Платёж не найден — возможно, уже обработан")
        await call.answer()
        return
    except Exception:
        log.exception("admin_reject_error", pending_id=callback_data.pending_id)
        await call.message.edit_text("❌ Ошибка при отклонении. Проверьте логи.")
        await call.answer()
        return

    await bot.send_message(
        chat_id=result.user_telegram_id,
        text="❌ Оплата не подтверждена. Обратитесь к @my7vpnadmin",
    )
    await call.message.edit_text("Отклонено")
    await call.answer()
    log.info("payment_rejected", pending_id=callback_data.pending_id)
