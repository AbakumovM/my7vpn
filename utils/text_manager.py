from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv(".env")


class TextManager:

    @staticmethod
    def get_start_message(user_name):
        return (
            f"👋 Привет, {user_name}!\n\n"
            "У вас пока нет активных устройств. Не беда! Давайте это исправим и настроим VPN для вашего устройства. 🚀\n\n"
            "📱 Выберите тип устройства, для которого вы хотите настроить VPN:\n"
        )

    @staticmethod
    def get_start_message_free_month(user_name):
        return (
            f"👋 Привет, {user_name}!\n\n"
            "🎉 <b>Поздравляем!</b> Вы получили бесплатный месяц подписки на одно устройство.\n\n"
            "📱 Выберите тип устройства, для которого вы хотите настроить VPN:\n"
        )

    @staticmethod
    def get_message_for_added_device():
        return "Выберите тип устройства, для которого вы хотите настроить VPN:"

    @staticmethod
    def get_start(user_name, count, balance):
        return (
            f"👋 Привет, {user_name}!\n\n"
            f"📱 <b>Активных устройств:</b> {count}\n\n"
            f"💰 <b>Ваш баланс за приведенных друзей:</b> {balance}₽\n\n"
            "Полную информацию о устройстве и подписке вы сможете найти, выбрав конкретное устройство.\n\n"
            "Важно! Заработайте 50₽ на баланс за каждого друга! Ваши друзья получат 1 месяц для одного устройства бесплатно.\n\n"
            "🔒 Пользуйтесь нашим VPN для защиты ваших данных в интернете\n\n"
            "❓ Встретили проблемы? Наши специалисты готовы помочь 24/7\n\n"
        )

    @staticmethod
    def get_message_devices(count: int):
        device_words = {
            0: "устройств",
            1: "устройство",
            2: "устройства",
            3: "устройства",
            4: "устройства",
            5: "устройств",
        }
        return f"<b>У вас активно {count} {device_words.get(count)}, цена зависит от выбранного вами тарифа.</b>\nПодробную информацию о стоимости вы сможете увидеть, выбрав нужное устройство.\n\n❌ <b>Важно!</b> Удаляйте из бота устройства, которые вы не используете, чтобы не платить за них абонентскую плату.\n\n👇 <b>Выберите нужное устройство из списка ниже, чтобы получить информацию о нем:</b>"

    @staticmethod
    def generate_device_info_message(data: dict):
        device_name = data["device_name"]
        end_date = data["end_date"]
        amount = data["amount"]
        payment_date = data["payment_date"]
        flag = False
        message = (
            f"📱 <b>Информация об устройстве:</b> {device_name}\n\n"
            f"🗓 <b>Дата окончания подписки:</b> {end_date}\n"
            f"💳 <b>Сумма последнего платежа:</b> {amount}₽\n"
            f"📅 <b>Дата последнего платежа:</b> {payment_date}\n\n"
            "❕ Убедитесь, что подписка активна, чтобы продолжить пользоваться услугами без перерывов.\n"
            '❕ Если у вас есть вопросы или нужно продлить подписку, нажмите на кнопку "Помощь" или напишите нам.'
        )

        if end_date:
            end_date_obj = datetime.strptime(end_date, "%d.%m.%Y")
            if (end_date_obj - datetime.now()).days <= 7:
                message += "\n\n⚠️ <b>Внимание! Ваша подписка истекает через несколько дней. Не забудьте продлить её.</b>"
                flag = True

        return message, flag

    @staticmethod
    def get_approve_payment(amount, payment_link, balance):
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
    def get_help_text():
        return "Выберите нужный пункт, чтобы получить подробную информацию:"

    @staticmethod
    def get_android_settings():
        return (
            "📱 <b>Подключение VPN на Android</b>\n\n"
            "1️⃣ <b>Скачайте приложение:</b>\n\n"
            '<a href="https://play.google.com/store/apps/details?id=com.v2raytun.android&pcampaignid=web_share">v2RayTun → Скачать в Play Market</a>\n\n'
            "2️⃣ <b>Установите и откройте приложение</b>\n\n"
            "<a>Разрешите необходимые доступы (если запрашивает).</a>\n\n"
            "3️⃣ <b>Получите конфигурацию VPN</b>\n\n"
            "<a>Админ пришлёт вам нужные настройки после проверки оплаты</a>\n\n"
            "4️⃣ <b>Импортируйте конфигурацию в приложение</b>\n\n"
            "<a>В приложении найдите кнопку ➕.</a>\n"
            "<a>Выберите QR или ссылку, которые вы получили от нашего админа</a>\n\n"
            "5️⃣ Добавьте настройки в приложение как указано в <a href='https://telegra.ph/Vazhnye-nastrojki-v2RayTun-04-17'>инструкции</a>\n\n"
            "5️⃣ <b>Подключитесь к VPN</b>\n\n"
            '<a>Нажмите кнопку "Подключиться" в приложении.</a>\n\n'
            "<b>Готово! Теперь ваш трафик защищён.</b>"
        )

    @staticmethod
    def get_computer_settings():
        return (
            "💻 <b>Подключение VPN на Компьютер</b>\n\n"
            "1️⃣ <b>Скачайте приложение в зависимости от вашей ОС:</b>\n\n"
            '<a href="https://apps.apple.com/ru/app/v2raytun/id6476628951">1. v2RayTun -> для Mac</a>\n'
            '<a href="https://m-1-3w5hsuiikq-ez.a.run.app/ru/downloads">2. AmneziaVPN -> для Windows</a>\n\n'
            "2️⃣ <b>Установите и откройте приложение</b>\n\n"
            "<a>Разрешите необходимые доступы (если запрашивает).</a>\n\n"
            "3️⃣ <b>Получите конфигурацию VPN</b>\n\n"
            "<a>Админ пришлёт вам нужные настройки после проверки оплаты</a>\n\n"
            "4️⃣ <b>Импортируйте конфигурацию в приложение</b>\n\n"
            "<a>В приложении найдите кнопку ➕.</a>\n"
            "<a>Выберите QR или ссылку, которые вы получили от нашего админа</a>\n\n"
            "5️⃣ Добавьте настройки в приложение как указано в <a href='https://telegra.ph/Vazhnye-nastrojki-v2RayTun-04-17'>инструкции для MAC</a> или <a href='https://telegra.ph/Vazhnye-nastrojki-dlya-AmneziaVPN-04-17'>инструкции для Windows</a>\n\n"
            "6️⃣ <b>Подключитесь к VPN</b>\n\n"
            '<a>Нажмите кнопку "Подключиться" в приложении.</a>\n\n'
            "<b>Готово! Теперь ваш трафик защищён.</b>"
        )

    @staticmethod
    def get_settings_iphone():
        return (
            "📱 <b>Подключение VPN на iPhone(iPad)</b>\n\n"
            "1️⃣ <b>Скачайте приложение (на ваш выбор):</b>\n\n"
            '<a href="https://apps.apple.com/ru/app/v2raytun/id6476628951">v2RayTun → Скачать в App Store</a>\n\n'
            "2️⃣ <b>Установите и откройте приложение</b>\n\n"
            "<a>Разрешите необходимые доступы (если запрашивает).</a>\n\n"
            "3️⃣ <b>Получите конфигурацию VPN</b>\n\n"
            "<a>Админ пришлёт вам нужные настройки после проверки оплаты</a>\n\n"
            "4️⃣ <b>Импортируйте конфигурацию в приложение</b>\n\n"
            "<a>В приложении найдите кнопку ➕.</a>\n"
            "<a>Выберите QR или ссылку, которые вы получили от нашего админа</a>\n\n"
            "5️⃣ Добавьте настройки в приложение как указано в <a href='https://telegra.ph/Vazhnye-nastrojki-v2RayTun-04-17'>инструкции</a>\n\n"
            "6️⃣ <b>Подключитесь к VPN</b>\n\n"
            '<a>Нажмите кнопку "Подключиться" в приложении.</a>\n\n'
            "<b>Готово! Теперь ваш трафик защищён.</b>"
        )

    @staticmethod
    def get_message_admin_error():
        return (
            "Заявка получена! Пока админ проверяет ваш VPN, попробуйте:\n\n"
            "1️⃣ Перезапустить приложение VPN или установить другое из /help.\n"
            "2️⃣ Проверить интернет-соединение.\n\n"
            "Если не поможет, мы уже в курсе и скоро вам поможем! 👨‍💻"
        )

    @staticmethod
    def get_full_info_payment(data: dict) -> str:
        month = {
            "1": "1 месяц",
            "3": "3 месяца",
            "6": "6 месяцев",
            "12": "12 месяцев",
        }
        return (
            f"🔐 <b>Подтвердите выбор VPN-подписки</b>\n\n"
            f"✔ <b>Устройство:</b> {data['device']}\n"
            f"✔ <b>Срок:</b> {month[data['period']]}\n"
            f"✔ <b>Стоимость:</b> {data['tariff']} ₽\n\n"
            f"✔ <b>Сумма к оплате с учетом бонусов:</b> {data['payment']} ₽\n\n"
            f"Хотите активировать VPN на этих условиях?\n\n"
            f"👉 После подтверждения вам придут инструкции по установке и настройке."
        )

    @staticmethod
    def get_message_invite_friend(referral_code: str) -> str:
        return (
            "🌟 <b>Программа «Приведи друга»</b>\n\n"
            "Вы получаете <b>50₽ за каждого друга</b>, а ваш друг — <b>месяц бесплатного VPN!</b>\n\n"
            "Как это работает:\n"
            "1️⃣ Поделитесь вашей персональной ссылкой 👇\n"
            "2️⃣ Друг регистрируется по ней и активирует VPN\n"
            "3️⃣ Вы получаете 50₽ на баланс, а друг — 30 дней бесплатно\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b> https://t.me/{os.getenv("BOT_NAME")}?start={referral_code}"
        )

    @staticmethod
    def get_message_success_free_month(device: str) -> str:
        return (
            "✅ Заявка отправлена администратору!\n\n"
            f"▫️ Ваше устройство: {device}\n"
            "▫️ Срок: 1 месяц\n"
            "Скоро с вами свяжутся для настройки.\n"
            "А пока вы можете:\n\n"
            "🎚️ <b>Зайти в раздел /help и выполнить шаги по настройке приложения</b>\n"
            "👉 <b>Пригласить друзей и заработать: /invite</b>\n"
            "🎁 За каждого друга:\n"
            "▪️ Вы получаете: 50₽ на баланс\n"
            "▪️ Друг получает: 1 месяц бесплатного VPN"
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
            f"Вам начислено: +50₽ реферальных бонусов\n\n"
            "💡 Как использовать бонусы:\n"
            "✔️ Автоматически применяются при оплате подписки\n"
        )


    @staticmethod
    def get_message_success_payment():
        return (
            '💳 <b>Спасибо! Ваша оплата принята.</b>\n\n'
            '🔹 Наш специалист свяжется с вами в ближайшее время для завершения подключения.\n\n'
            '📌 Пока вы можете перейти в раздел <b>/help</b> и выполнить шаги из инструкции для вашего устройства.'    
        )

bot_repl = TextManager()
