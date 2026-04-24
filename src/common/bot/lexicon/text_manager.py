from src.infrastructure.config import app_config


class TextManager:
    @staticmethod
    def get_main_menu_active(user_name: str, end_date: str, used: int, limit: int, balance: int) -> str:
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"✅ Подписка активна до {end_date}\n"
            f"📱 Устройств: {used} / {limit}\n"
            f"💰 Баланс: {balance}₽"
        )

    @staticmethod
    def get_main_menu_new(user_name: str) -> str:
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"У вас пока нет активной подписки.\n"
            f"Подключите VPN и защитите свои данные! 🚀"
        )

    @staticmethod
    def get_start_message_free_month(user_name):
        return (
            f"👋 Привет, {user_name}!\n\n"
            "🎉 <b>Поздравляем!</b> Вы получили бесплатные 7 дней подписки на одно устройство.\n\n"
            "ВАЖНО☝️ Проверь наличие @никнейма в своем профиле. Если его нет, админ не сможет написать и выдать доступ!\n\n"
            "📱 Выберите тип устройства, для которого вы хотите настроить VPN:\n"
        )

    @staticmethod
    def get_message_for_added_device():
        return "Выберите тип устройства, для которого вы хотите настроить VPN:"

    @staticmethod
    def get_subscription_info(
        end_date: str, device_limit: int, last_payment: int | None, subscription_url: str | None,
        days_left: int | None = None,
    ) -> str:
        text = "🔐 <b>Ваша подписка</b>\n\n"

        if days_left is not None and days_left <= 7:
            text += f"📅 Активна до: <b>{end_date}</b> ({days_left} дн.!)\n"
            text += "⚠️ <b>Продлите подписку, чтобы VPN не отключился</b>\n\n"
        else:
            text += f"📅 Активна до: <b>{end_date}</b>\n"

        text += f"📱 Устройств: <b>{device_limit}</b>\n"
        if last_payment is not None:
            text += f"💳 Последний платёж: <b>{last_payment}₽</b>\n"

        if subscription_url:
            text += f"\n🔗 <b>Ваш ключ для happ:</b>\n<code>{subscription_url}</code>"

        return text

    @staticmethod
    def get_no_subscription() -> str:
        return "У вас пока нет активной подписки."

    @staticmethod
    def get_choose_device_count() -> str:
        return (
            "📱 <b>Сколько устройств подключить?</b>\n\n"
            "Одна подписка — на все ваши устройства: телефон, компьютер, телевизор."
        )

    @staticmethod
    def get_choose_tariff(device_limit: int) -> str:
        device_emoji = "📱" * device_limit
        device_word = {1: "устройство", 2: "устройства", 3: "устройства"}
        return (
            f"⏳ <b>Выберите срок подписки</b>\n\n"
            f"{device_emoji} {device_limit} {device_word[device_limit]}"
        )

    @staticmethod
    def get_confirm_payment(
        device_limit: int, duration: int, price: int, bonus: int, total: int,
    ) -> str:
        month_word = {1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев"}
        text = (
            f"🔐 <b>Подтвердите подписку</b>\n\n"
            f"📱 Устройств: <b>{device_limit}</b>\n"
            f"⏳ Срок: <b>{month_word.get(duration, f'{duration} мес')}</b>\n"
            f"💰 Стоимость: <b>{price}₽</b>\n"
        )
        if bonus > 0:
            text += f"🎁 Бонус: <b>-{bonus}₽</b>\n"
        text += f"\n💳 К оплате: <b>{total}₽</b>"
        return text

    @staticmethod
    def get_friends_screen(invited_count: int, total_earned: int, balance: int) -> str:
        return (
            f"👫 <b>Пригласи друга</b>\n\n"
            f"Ты получаешь <b>50₽</b>, друг — <b>7 дней VPN бесплатно</b>\n\n"
            f"📊 <b>Твоя статистика:</b>\n"
            f"Приглашено: <b>{invited_count}</b>\n"
            f"Заработано: <b>{total_earned}₽</b>\n"
            f"💰 Баланс: <b>{balance}₽</b>"
        )

    @staticmethod
    def get_instruction(platform: str) -> str:
        instructions = {
            "android_phone": (
                "📱 <b>Подключение на Android</b>\n\n"
                "1️⃣ Скачайте <b>happ</b>:\n"
                '<a href="https://play.google.com/store/apps/details?id=app.hiddify.com">→ Google Play</a>\n\n'
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "ios": (
                "🍏 <b>Подключение на iPhone / iPad</b>\n\n"
                "1️⃣ Скачайте <b>happ</b>:\n"
                '<a href="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532">→ App Store</a>\n\n'
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "windows": (
                "💻 <b>Подключение на Windows</b>\n\n"
                "1️⃣ Скачайте <b>happ</b>:\n"
                '<a href="https://apps.microsoft.com/detail/9pdfnl3qv2s5">→ Microsoft Store</a>\n\n'
                "2️⃣ Установите и откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "macos": (
                "💻 <b>Подключение на MacOS</b>\n\n"
                "1️⃣ Скачайте <b>happ</b>:\n"
                '<a href="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532">→ App Store</a>\n\n'
                "2️⃣ Установите и откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "tv": (
                "📺 <b>Подключение на Android TV</b>\n\n"
                "1️⃣ Скачайте <b>happ</b> из Google Play на ТВ\n\n"
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Добавьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
        }
        return instructions.get(platform, "Платформа не найдена")

    @staticmethod
    def get_approve_payment_link(amount: int, confirmation_url: str) -> str:
        return (
            f"💳 <b>Оплата подписки</b>\n\n"
            f"Сумма: <b>{amount}₽</b>\n\n"
            f'<a href="{confirmation_url}">👉 Ссылка для оплаты</a>\n\n'
            f"✅ После оплаты подписка активируется автоматически. "
            f"Ничего нажимать не нужно!"
        )

    @staticmethod
    def get_approve_payment(amount, payment_link):
        return (
            f"💳 <b>Оплата подписки</b>\n\n"
            f"Сумма к оплате по тарифу: <b>{amount}₽</b>\n\n"
            f"Вы можете оплатить:\n"
            f"1. По QR-коду выше.\n"
            f'2. По <a href="{payment_link}">ссылке.</a>\n\n'
            f'⚠️ <b>Важно!</b> После оплаты нажмите кнопку <b>"Я оплатил"</b>, чтобы мы могли обработать ваш заказ.\n'
            f"Специалист свяжется с вами для дальнейшего подключения."
        )

    @staticmethod
    def get_message_admin_error():
        return (
            "Заявка получена! Пока админ проверяет ваш VPN, попробуйте:\n\n"
            "1️⃣ Перезапустить приложение VPN.\n"
            "2️⃣ Проверить интернет-соединение.\n\n"
            "Если не поможет, мы уже в курсе и скоро вам поможем! 👨‍💻"
        )

    @staticmethod
    def get_full_info_payment(device, duration, finally_payment, payment) -> str:
        month = {
            1: "1 месяц",
            3: "3 месяца",
            6: "6 месяцев",
            12: "12 месяцев",
        }
        return (
            f"🔐 <b>Подтвердите выбор VPN-подписки</b>\n\n"
            f"✔ <b>Устройство:</b> {device}\n"
            f"✔ <b>Срок:</b> {month.get(duration)}\n"
            f"✔ <b>Стоимость:</b> {payment} ₽\n\n"
            f"✔ <b>Сумма к оплате с учетом бонусов:</b> {finally_payment} ₽\n\n"
            f"Хотите активировать VPN на этих условиях?\n\n"
            f"👉 После подтверждения вам придут инструкции по установке и настройке."
        )

    @staticmethod
    def get_message_invite_friend(referral_code: str) -> str:
        return (
            "🌟 <b>Программа «Приведи друга»</b>\n\n"
            "Вы получаете <b>50₽ за каждого друга</b>, а ваш друг — <b>7 дней бесплатного VPN!</b>\n\n"
            "Как это работает:\n"
            "1️⃣ Поделитесь вашей персональной ссылкой 👇\n"
            "2️⃣ Друг регистрируется по ней и активирует VPN\n"
            "3️⃣ Вы получаете 50₽ на баланс, а друг — 7 дней бесплатно\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b> https://t.me/{app_config.bot.bot_name}?start={referral_code}"
        )

    @staticmethod
    def get_message_success_free_month(device: str) -> str:
        return (
            "✅ Заявка отправлена администратору!\n\n"
            f"▫️ Ваше устройство: {device}\n"
            "▫️ Срок: 1 месяц\n"
            "Скоро с вами свяжутся для настройки.\n\n"
            "<b>‼️ВАЖНО! Проверьте, чтоб у вас было указано 'Имя пользователя' в настройках\n"
            "В противном случае наш админ не сможет вам написать</b>\n\n"
            "А пока вы можете:\n\n"
            "🎚️ <b>Зайти в раздел /help и выполнить шаги по настройке приложения</b>\n"
            "👉 <b>Пригласить друзей и заработать: /invite</b>\n"
            "🎁 За каждого друга:\n"
            "▪️ Вы получаете: 50₽ на баланс\n"
            "▪️ Друг получает: 7 дней бесплатного VPN"
        )

    @staticmethod
    def get_message_error_referral():
        return (
            "🔐 <b>Упс... Кажется, ссылка не работает!</b>\n\n"
            "К сожалению, мы не смогли найти пользователя, который пригласил вас. Возможно:\n\n"
            "▫️ Ссылка устарела или содержит ошибку\n"
            "▫️ Пригласивший вас пользователь удалил свой аккаунт\n"
            "▫️ Была допущена опечатка в ссылке\n\n"
            "Что можно сделать:\n"
            "1️⃣ Попросите друга прислать новую ссылку из меню бота\n"
            "2️⃣ Проверьте, правильно ли скопирована ссылка\n"
            "3️⃣ Если проблема повторяется - напишите в поддержку: @my7vpnadmin\n\n"
            "P.S. Настоящие реферальные ссылки выглядят так:\n"
            "https://t.me/myvpn7bot?start=ref_ABC123 (только английские буквы и цифры)"
        )

    @staticmethod
    def get_message_new_user_referral() -> str:
        return (
            "🎉 Поздравляем! Ваш друг только что активировал VPN по вашей ссылке!\n\n"
            "Вам начислено: +50₽ реферальных бонусов\n\n"
            "💡 Как использовать бонусы:\n"
            "✔️ Автоматически применяются при оплате подписки\n"
        )

    @staticmethod
    def get_message_success_payment():
        return (
            "💳 <b>Спасибо! Ваша оплата принята.</b>\n\n"
            "🔹 Наш специалист свяжется с вами в ближайшее время для завершения подключения.\n\n"
            "<b>‼️ВАЖНО! Проверьте, чтоб у вас было указано 'Имя пользователя' в настройках\n"
            "В противном случае наш админ не сможет вам написать</b>\n\n"
            "📌 Пока вы можете перейти в раздел <b>/help</b> и выполнить шаги из инструкции для вашего устройства."
        )

    @staticmethod
    def get_message_success_payment_update():
        return "💳 <b>Спасибо! Ваша оплата принята.</b>\n\n🔹 Подписка продлена!\n\n"

    @staticmethod
    def send_messages_end_pay(device_name: str) -> str:
        return (
            f"⏳ Внимание! Подписка на устройстве <b>{device_name}</b> заканчивается сегодня.\n\n"
            "Чтобы продолжить пользоваться стабильным и быстрым VPN без перерывов — просто продлите подписку:\n\n"
            "🔹 Перейдите в раздел <b>«Мои устройства»</b>\n"
            f"🔹 Выберите устройство <b>{device_name}</b>\n"
            "🔹 Нажмите <b>«Продлить»</b> и выберите удобный тариф\n\n"
            "🔒 Продление займёт всего пару секунд — и вы снова под надёжной защитой.\n\n"
            "Если нужна помощь — просто напишите  @my7vpnadmin. Мы всегда на связи! 💬\n\n"
        )

    @staticmethod
    def send_messages_cancel_choice() -> str:
        return "Жаль! Но вы всегда можете вернуться к этому, когда будет удобно 👍"

    @staticmethod
    def send_messages_for_admin_update(
        username: str, user_id: int, device: str, duration: int, payment: int
    ) -> str:
        """
        Generates an admin notification message about a user's VPN subscription renewal.

        Args:
            username (str): Username of the subscriber
            user_id (int): Unique identifier of the subscriber
            device (str): Type of device for VPN subscription
            duration (int): Subscription duration period
            payment (int): Payment amount received

        Returns:
            str: Formatted message containing subscription renewal details in Russian
        """
        return (
            f"Пользователь продлил подписку VPN!\n"
            f"👤 Имя: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"📋 Критерии: девайс {device}, срок {duration}, тариф {payment}, сколько оплатил {payment}"
        )

    @staticmethod
    def send_message_admin_new_device(
        username: str, user_id: int, device: str, duration: int, payment: int
    ) -> str:
        return (
            f"Пользователь хочет подключить VPN!\n"
            f"👤 Имя: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"📋 Критерии: девайс {device}, срок {duration}, сколько оплатил {payment}"
        )

    @staticmethod
    def send_message_admin_new_user_referral(
        username: str, user_id: int, referral_id: int, device: str
    ) -> str:
        return (
            f"Пользователь хочет подключить VPN по реферальной ссылке!\n"
            f"👤 Имя: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"🆔 Кто пригласил: {referral_id}"
            f"📋 Критерии: девайс {device}"
        )


bot_repl = TextManager()
