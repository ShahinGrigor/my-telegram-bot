import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from collections import defaultdict
from datetime import datetime, timedelta
import html
import re

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Проверка токена
if not BOT_TOKEN:
    logging.error("Токен бота не найден! Проверьте файл .env")
    exit(1)


# Защита от флуда
class RateLimiter:
    def __init__(self):
        self.user_requests = defaultdict(list)

    def is_allowed(self, user_id: int, limit: int = 5, window: int = 60) -> bool:
        now = datetime.now()
        user_requests = self.user_requests[user_id]

        user_requests[:] = [req_time for req_time in user_requests
                            if now - req_time < timedelta(seconds=window)]

        if len(user_requests) >= limit:
            return False

        user_requests.append(now)
        return True


rate_limiter = RateLimiter()


# Декоратор для ограничения запросов
def rate_limit(limit: int = 5, window: int = 60):
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id

            if not rate_limiter.is_allowed(user_id, limit, window):
                if update.callback_query:
                    await update.callback_query.answer("⚠️ Слишком много запросов. Подождите минуту.", show_alert=True)
                else:
                    await update.message.reply_text("⚠️ Слишком много запросов. Подождите минуту.")
                return

            return await func(update, context)

        return wrapper

    return decorator


# Защита административных функций
def admin_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            logging.warning(f"Неавторизованный доступ: {user_id}")

            if update.callback_query:
                await update.callback_query.answer("❌ Доступ запрещен", show_alert=True)
            else:
                await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        return await func(update, context)

    return wrapper


# Очистка пользовательского ввода
def sanitize_input(text: str, max_length: int = 100) -> str:
    if not text:
        return ""

    text = text[:max_length]
    text = html.escape(text)

    dangerous_patterns = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"onclick|onload|onerror",
    ]

    for pattern in dangerous_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


print("🔧 Базовые настройки безопасности загружены!")

# Данные для демо-каталога (временное хранилище)
products = {
    1: {"name": "iPhone 15", "price": 999, "category": "📱 Электроника"},
    2: {"name": "MacBook Air", "price": 1299, "category": "💻 Ноутбуки"},
    3: {"name": "Python для начинающих", "price": 29, "category": "📚 Книги"},
}

services = {
    1: "💇 Стрижка",
    2: "💅 Маникюр",
    3: "✂️ Бритье"
}

# Временное хранилище (в реальном проекте используйте БД)
users_data = {}
carts = {}
bookings = {}


# Клавиатуры
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍️ Мини-магазин", callback_data="catalog")],
        [InlineKeyboardButton("📅 Запись на услугу", callback_data="booking")],
        [InlineKeyboardButton("❓ Пройти тест", callback_data="quiz")],
        [InlineKeyboardButton("💰 Курс валют", callback_data="currency")],
        [InlineKeyboardButton("ℹ️ О разработчике", callback_data="about"),
         InlineKeyboardButton("📞 Связаться", callback_data="contact")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Обработчики команд
@rate_limit()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users_data[user_id] = {"first_seen": datetime.now(), "username": update.effective_user.username}

    welcome_text = """
🤖 Добро пожаловать в демонстрационного бота!

Этот бот создан чтобы показать возможности телеграм ботов для вашего бизнеса.

Выберите один из разделов ниже чтобы увидеть функционал:
    """

    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
    logging.info(f"Новый пользователь: {user_id}")


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Главное меню:", reply_markup=get_main_keyboard())


# Информация о разработчике
async def about_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """
👨‍💻 *О разработчике*

Я создаю телеграм боты под ключ для бизнеса.

🛠️ *Мои компетенции:*
• Python + python-telegram-bot
• Интеграция с API
• Системы бронирования и E-commerce
• Боты с AI и машинным обучением

📈 *Результаты для клиентов:*
• Автоматизация рутинных операций
• Увеличение конверсии на 20-40%
• Круглосуточное обслуживание клиентов


*Замените эту информацию на свою!*
    """

    keyboard = [
        [InlineKeyboardButton("📞 Обсудить проект", url="https://t.me/GrigoryShag")],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """
📞 *Связаться с разработчиком*

💬 Напишите мне прямо в Telegram: @GrigoryShag

📧 Или отправьте email: gregoryshaginyan@yandex.ru

⏱️ *Время ответа:* обычно в течение 1 часа

*Готов обсудить ваш проект!*


    """

    keyboard = [
        [InlineKeyboardButton("💬 Написать в Telegram", url="https://t.me/GrigoryShag")],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


print("🎮 Основные обработчики загружены!")


# Модуль магазина
def get_categories_keyboard():
    categories = set(product["category"] for product in products.values())
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category, callback_data=f"category_{category}")])
    keyboard.append([InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_products_keyboard(category):
    keyboard = []
    for product_id, product in products.items():
        if product["category"] == category:
            keyboard.append([InlineKeyboardButton(
                f"{product['name']} - ${product['price']}",
                callback_data=f"product_{product_id}"
            )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="catalog")])
    return InlineKeyboardMarkup(keyboard)


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = "🛍️ *Мини-магазин*\n\nВыберите категорию товаров:"
    await query.edit_message_text(text, reply_markup=get_categories_keyboard(), parse_mode='Markdown')


async def show_category_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.replace("category_", "")
    text = f"Товары в категории *{category}*:"

    await query.edit_message_text(text, reply_markup=get_products_keyboard(category), parse_mode='Markdown')


async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.replace("product_", ""))
    user_id = query.from_user.id

    if user_id not in carts:
        carts[user_id] = {}

    if product_id in carts[user_id]:
        carts[user_id][product_id] += 1
    else:
        carts[user_id][product_id] = 1

    product_name = products[product_id]["name"]
    await query.message.reply_text(f"✅ {product_name} добавлен в корзину!")


async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in carts or not carts[user_id]:
        text = "🛒 Ваша корзина пуста"
        keyboard = [[InlineKeyboardButton("⬅️ Назад к категориям", callback_data="catalog")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "🛒 *Ваша корзина:*\n\n"
    total = 0

    for product_id, quantity in carts[user_id].items():
        product = products[product_id]
        subtotal = product["price"] * quantity
        total += subtotal
        text += f"{product['name']} x{quantity} - ${subtotal}\n"

    text += f"\n💵 *Итого: ${total}*"

    keyboard = [
        [InlineKeyboardButton("📦 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("⬅️ Продолжить покупки", callback_data="catalog")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_name = query.from_user.full_name

    if user_id not in carts or not carts[user_id]:
        await query.message.reply_text("❌ Корзина пуста!")
        return

    # Имитация оформления заказа
    total = sum(products[pid]["price"] * qty for pid, qty in carts[user_id].items())

    # Отправка "администратору" (вам)
    admin_text = f"🆕 НОВЫЙ ЗАКАЗ!\nОт: {user_name}\nID: {user_id}\nСумма: ${total}"
    logging.info(admin_text)

    # Очистка корзины
    carts[user_id] = {}

    text = f"""
✅ *Заказ оформлен!*

Спасибо за ваш заказ на сумму *${total}*.
Наш менеджер свяжется с вами в ближайшее время для подтверждения.

*Это демонстрация функционала интернет-магазина в Telegram!*
    """

    await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    carts[user_id] = {}

    await query.message.reply_text("🗑️ Корзина очищена!")
    await show_catalog(update, context)


print("🛍️ Модуль магазина загружен!")


# Модуль бронирования
async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for service_id, service_name in services.items():
        keyboard.append([InlineKeyboardButton(service_name, callback_data=f"book_service_{service_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])

    text = "📅 *Запись на услугу*\n\nВыберите услугу:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    service_id = int(query.data.replace("book_service_", ""))
    context.user_data["booking_service"] = service_id
    service_name = services[service_id]

    # Простой выбор времени (в реальном боте используйте календарь)
    times = ["10:00", "11:00", "14:00", "15:00", "16:00"]
    keyboard = []

    for time in times:
        keyboard.append([InlineKeyboardButton(f"{time}", callback_data=f"book_time_{time}")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="booking")])

    text = f"📅 Выбрана услуга: *{service_name}*\n\nВыберите удобное время:"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    time_str = query.data.replace("book_time_", "")
    service_id = context.user_data["booking_service"]

    # Сохраняем бронь
    user_id = query.from_user.id
    if user_id not in bookings:
        bookings[user_id] = []

    booking_info = {
        "service": services[service_id],
        "time": time_str,
        "timestamp": datetime.now()
    }
    bookings[user_id].append(booking_info)

    # Отправка "администратору"
    admin_text = f"📅 НОВАЯ ЗАПИСЬ!\nКлиент: {query.from_user.full_name}\nУслуга: {services[service_id]}\nВремя: {time_str}"
    logging.info(admin_text)

    text = f"""
✅ *Запись подтверждена!*

📋 Услуга: *{services[service_id]}*
⏰ Время: *{time_str}*

Наш администратор свяжется с вами для подтверждения.

*Это демонстрация системы бронирования в Telegram!*
    """

    await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')


# Админ-панель
@admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("👨‍💻 *Панель администратора*", reply_markup=get_admin_keyboard(),
                                        parse_mode='Markdown')
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("👨‍💻 *Панель администратора*", reply_markup=get_admin_keyboard(),
                                      parse_mode='Markdown')


@admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    total_users = len(users_data)
    total_carts = len([c for c in carts.values() if c])
    total_bookings = sum(len(b) for b in bookings.values())

    text = f"""
📊 *Статистика бота*

👥 Всего пользователей: *{total_users}*
🛒 Активных корзин: *{total_carts}*
📅 Всего записей: *{total_bookings}*

*Демонстрация аналитики для администратора*
    """

    keyboard = [
        [InlineKeyboardButton("⬅️ В админку", callback_data="admin_panel")],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


print("📅 Модуль бронирования и админ-панели загружен!")


# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Ошибка: {context.error}", exc_info=True)

    try:
        error_message = "⚠️ Произошла ошибка. Мы уже работаем над ее исправлением."

        if update and update.effective_chat:
            if update.callback_query:
                await update.callback_query.message.reply_text(error_message)
            else:
                await update.message.reply_text(error_message)
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения об ошибке: {e}")


# Главная функция
def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", admin_panel))

        # Обработчики callback'ов
        application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
        application.add_handler(CallbackQueryHandler(show_catalog, pattern="^catalog$"))
        application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
        application.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
        application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
        application.add_handler(CallbackQueryHandler(start_booking, pattern="^booking$"))
        application.add_handler(CallbackQueryHandler(about_developer, pattern="^about$"))
        application.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
        application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
        application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))

        # Категории и товары
        application.add_handler(CallbackQueryHandler(show_category_products, pattern="^category_"))
        application.add_handler(CallbackQueryHandler(add_to_cart, pattern="^product_"))

        # Бронирование
        application.add_handler(CallbackQueryHandler(select_service, pattern="^book_service_"))
        application.add_handler(CallbackQueryHandler(confirm_booking, pattern="^book_time_"))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        # Запуск бота
        logging.info("🤖 Бот запускается...")
        print("=" * 50)
        print("🎉 Бот успешно запущен!")
        print("📱 Перейдите в Telegram и найдите вашего бота")
        print("🚀 Напишите команду /start чтобы начать")
        print("=" * 50)

        application.run_polling()

    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске: {e}")
        print(f"❌ Ошибка запуска: {e}")
        print("🔧 Проверьте:")
        print("   - Токен бота в файле .env")
        print("   - Подключение к интернету")
        print("   - Установлены ли все библиотеки")


if __name__ == '__main__':
    main()