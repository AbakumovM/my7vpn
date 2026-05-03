from datetime import date, datetime


class TextManager:
    @staticmethod
    def get_main_menu_active(user_name: str, end_date: str, used: int, limit: int, balance: int) -> str:
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"Твоя защита активна.\n\n"
            f"✅ Подписка до {end_date}\n"
            f"📱 Устройств: {used} / {limit}\n"
            f"💰 Баланс: {balance}₽\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎁 Пригласи друга — получи 50₽ на баланс.\n"
            f"Друг получит 5 дней бесплатно.\n\n"
            f"💻 Личный кабинет в разработке — скоро будет."
        )

    @staticmethod
    def get_main_menu_new(user_name: str) -> str:
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"У вас пока нет активной подписки.\n\n"
            f"Что даёт ZEVSgate:\n"
            f"• До 3 устройств по одной подписке\n"
            f"• Несколько серверов — и мы их расширяем\n"
            f"• Работает на телефоне, ноутбуке, телевизоре\n\n"
            f"🎁 А ещё — приглашайте друзей:\n"
            f"• Вы получаете 50₽ на баланс\n"
            f"• Друг получает 5 дней бесплатно\n\n"
            f"👉 Выберите тариф или пригласите друга 🚀"
        )

    @staticmethod
    def get_start_message_free_month(user_name: str) -> str:
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"🎉 <b>Поздравляем!</b> Вы получили 5 дней ZEVSgate бесплатно.\n"
            f"Активируйте подписку и пользуйтесь на любом устройстве.\n\n"
            f"<b>Что такое ZEVSgate?</b>\n"
            f"• Быстрый и надёжный VPN\n"
            f"• До 3 устройств по одной подписке\n"
            f"• Несколько серверов — и мы их расширяем\n"
            f"• Работает везде: телефон, ноутбук, телевизор\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎁 <b>Приглашай друзей и получай бонусы</b>\n"
            f"➜ Ты получаешь <b>50₽</b> на баланс\n"
            f"➜ Друг получает <b>5 дней бесплатно</b>\n\n"
            
        )

    @staticmethod
    def get_subscription_info(
        end_date: str, device_limit: int, last_payment: int | None, subscription_url: str | None,
        days_left: int | None = None,
    ) -> str:
        text = "🔐 <b>ZEVSgate — ваша подписка</b>\n\n"

        if days_left is not None and days_left <= 7:
            text += f"📅 Активна до: <b>{end_date}</b> (осталось {days_left} дн.)\n"
            text += "⚠️ <b>Скоро закончится. Продлите, чтобы оставаться под защитой.</b>\n\n"
        else:
            text += f"📅 Активна до: <b>{end_date}</b>\n\n"

        text += f"📱 Устройств в подписке: <b>{device_limit}</b>\n"
        if last_payment is not None:
            text += f"💳 Последний платёж: <b>{last_payment}₽</b>\n"

        if subscription_url:
            text += f"\n🔗 <b>Ключ подписки (для настройки):</b>\n<code>{subscription_url}</code>\n\n"
            text += "⚡ Скопируйте его и вставьте в приложение (Happ)"

        return text

    @staticmethod
    def get_no_subscription() -> str:
        return "У вас пока нет активной подписки."

    @staticmethod
    def get_hwid_devices_screen(devices: list[dict]) -> str:
        if not devices:
            return (
                "📱 <b>Подключённые устройства</b>\n\n"
                "Нет подключённых устройств.\n\n"
                "Устройства появятся здесь после первого подключения к VPN."
            )
        text = f"📱 <b>Подключённые устройства</b> ({len(devices)}):\n\n"
        for d in devices:
            model = d.get("device_model") or "Неизвестное устройство"
            platform = d.get("platform") or ""
            os_ver = d.get("os_version") or ""
            info = " · ".join(filter(None, [platform, os_ver]))
            text += f"▪️ <b>{model}</b>"
            if info:
                text += f" <i>({info})</i>"
            text += "\n"
        text += "\nНажмите на устройство, чтобы удалить его."
        return text

    @staticmethod
    def get_hwid_delete_all_confirm() -> str:
        return (
            "⚠️ <b>Удалить все устройства?</b>\n\n"
            "Все подключённые устройства будут сброшены. "
            "Они смогут переподключиться заново при следующем запуске VPN."
        )

    @staticmethod
    def get_choose_device_count() -> str:
        return (
            "📱 <b>Сколько устройств подключить?</b>\n\n"
            "Одна подписка ZEVSgate — до 3 устройств:\n"
            "телефон, компьютер, телевизор — всё сразу.\n\n"
            "👉 Выберите количество, которое вам нужно:"
        )

    @staticmethod
    def get_choose_tariff(device_limit: int) -> str:
        device_emoji = "📱" * device_limit
        device_word = {1: "устройство", 2: "устройства", 3: "устройства"}
        return (
            f"⏳ <b>Выберите срок подписки ZEVSgate</b>\n\n"
            f"{device_emoji} {device_limit} {device_word[device_limit]}\n\n"
            f"Доступны варианты: 1, 3, 6 или 12 месяцев.\n"
            f"Чем дольше срок — тем выгоднее.\n\n"
            f"👉 Нажмите на подходящий вариант ниже:"
        )

    @staticmethod
    def get_confirm_payment(
        device_limit: int, duration: int, price: int, bonus: int, total: int,
    ) -> str:
        month_word = {1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев"}
        text = (
            f"🔐 <b>Подтвердите подписку ZEVSgate</b>\n\n"
            f"📱 Устройств: <b>{device_limit}</b>\n"
            f"⏳ Срок: <b>{month_word.get(duration, f'{duration} мес')}</b>\n"
            f"💰 Стоимость: <b>{price}₽</b>\n"
        )
        if bonus > 0:
            text += f"🎁 Бонус: <b>-{bonus}₽</b>\n"
        text += f"\n💳 К оплате: <b>{total}₽</b>"
        return text

    @staticmethod
    def get_friends_screen(invited_count: int, total_earned: int, balance: int, referral_link: str) -> str:
        return (
            f"👫 <b>Пригласи друга</b>\n\n"
            f"Ты получаешь <b>50₽</b>, друг — <b>5 дней VPN бесплатно</b>\n\n"
            f"📊 <b>Твоя статистика:</b>\n"
            f"Приглашено: <b>{invited_count}</b>\n"
            f"🎁 Ожидаемый бонус: <b>{total_earned}₽</b>\n"
            f"(придёт на баланс когда друг оплатит подписку)\n"
            f"💰 Баланс: <b>{balance}₽</b>\n\n"
            f"🔗 Твоя ссылка (нажми, чтобы скопировать):\n"
            f"<code>{referral_link}</code>"
        )

    @staticmethod
    def get_instruction(platform: str) -> str:
        instructions = {
            "android_phone": (
                "📱 <b>Подключение на Android</b>\n\n"
                "1️⃣ Скачайте <b>Happ</b>:\n"
                '<a href="https://play.google.com/store/apps/details?id=com.happproxy">→ Google Play</a>\n'
                '<a href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk">→ APK (если нет Play)</a>\n\n'
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "ios": (
                "🍏 <b>Подключение на iPhone / iPad</b>\n\n"
                "1️⃣ Скачайте <b>Happ</b>:\n"
                '<a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">→ App Store (Россия)</a>\n'
                '<a href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215">→ App Store (другие регионы)</a>\n\n'
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "windows": (
                "💻 <b>Подключение на Windows</b>\n\n"
                "1️⃣ Скачайте <b>Happ</b>:\n"
                '<a href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe">→ Скачать (.exe)</a>\n\n'
                "2️⃣ Установите и откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "macos": (
                "💻 <b>Подключение на MacOS</b>\n\n"
                "1️⃣ Скачайте <b>Happ</b>:\n"
                '<a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">→ App Store (Россия)</a>\n'
                '<a href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215">→ App Store (другие регионы)</a>\n'
                '<a href="https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.macOS.universal.dmg">→ DMG (прямая загрузка)</a>\n\n'
                "2️⃣ Установите и откройте приложение\n\n"
                "3️⃣ Нажмите <b>➕</b> и вставьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
            "tv": (
                "📺 <b>Подключение на Android TV</b>\n\n"
                "1️⃣ Скачайте <b>Happ</b>:\n"
                '<a href="https://play.google.com/store/apps/details?id=com.happproxy">→ Google Play</a>\n'
                '<a href="https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk">→ APK</a>\n\n'
                "2️⃣ Откройте приложение\n\n"
                "3️⃣ Добавьте ваш ключ подписки\n\n"
                "4️⃣ Нажмите <b>«Подключиться»</b>\n\n"
                "✅ <b>Готово!</b> VPN активен."
            ),
        }
        return instructions.get(platform, "Платформа не найдена")

    @staticmethod
    def get_approve_payment_link(amount: int, confirmation_url: str, action: str = "new") -> str:
        if action == "renew":
            hint = "✅ После оплаты подписка продлится автоматически. Ничего нажимать не нужно!"
        else:
            hint = (
                "✅ После оплаты подписка активируется автоматически.\n\n"
                "📥 Скачайте приложение <b>Happ</b> и вставьте туда вашу ссылку — "
                "она придёт в этот чат сразу после оплаты."
            )
        return (
            f"💳 <b>Оплата подписки</b>\n\n"
            f"Сумма: <b>{amount}₽</b>\n\n"
            f'<a href="{confirmation_url}">👉 Ссылка для оплаты</a>\n\n'
            f"{hint}"
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
            "▪️ Друг получает: 5 дней бесплатного VPN"
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
            "🎉 Отлично! Ваш друг подключил ZEVSgate по вашей ссылке.\n\n"
            "💰 Вам начислено: +50₽ на баланс\n\n"
            "💡 Бонусы сработают автоматически при следующей оплате подписки.\n"
            "Никаких промокодов — просто пользуйтесь."
        )

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
    def subscription_expiry_notice(days_before: int, end_date: date) -> str:
        formatted = end_date.strftime("%d.%m.%Y")
        if days_before == 7:
            return (
                f"📅 ZEVSgate: ваша подписка истекает через 7 дней ({formatted}).\n"
                f"Продлите заранее — оставайтесь под защитой без пауз."
            )
        if days_before == 3:
            return (
                f"⏳ ZEVSgate: до окончания подписки 3 дня ({formatted}).\n"
                f"Лучше продлить сейчас, чтобы не забыть."
            )
        if days_before == 1:
            return (
                f"⚠️ ZEVSgate: подписка истекает завтра ({formatted}).\n"
                f"Продлите сегодня — это займёт минуту."
            )
        # days_before == 0
        return (
            "🔴 ZEVSgate: сегодня последний день подписки.\n"
            "Продлите доступ, чтобы VPN продолжал работать."
        )


    @staticmethod
    def migration_notification(end_date: datetime) -> str:
        return (
            f"🚀 ZEVSgate — это новый уровень вашего VPN!\n\n"
            f"Мы обновили сервис. Теперь он быстрее, надёжнее и удобнее.\n\n"
            f"<b>Что изменилось:</b>\n"
            f"• <b>Одна подписка</b> вместо отдельных ключей (сейчас на 1 устройство, при продлении — до 3)\n"
            f"• <b>Полный контроль устройств</b> — добавляйте и удаляйте сами\n"
            f"• <b>Выбор сервера</b> для подключения\n"
            f"• Новое приложение <b>happ</b>\n"
            f"• Скорость и надёжность выросли\n\n"
            f"🎁 <b>Реферальная программа сохранена!</b>\n"
            f"• <b>Вам:</b> 50₽ за каждого приглашённого друга\n"
            f"• <b>Другу:</b> 5 дней бесплатного VPN\n\n"
            f"✅ Ваш срок действия сохраняется: до <b>{end_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"💻 В ближайшее время появится <b>личный кабинет</b> — управление без Telegram.\n\n"
            f"👇 Нажмите на кнопку, чтобы получить новый ключ подписки."
        )


bot_repl = TextManager()
