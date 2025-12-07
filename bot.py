#!/usr/bin/env python3
"""
Telegram Bot Demo - Демонстрационный бот для продажи услуг
Версия для python-telegram-bot v21.x
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# Загружаем переменные окружения
load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Проверка конфигурации
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== КЛАССЫ ДЛЯ БЕЗОПАСНОСТИ ====================
class RateLimiter:
    """Защита от флуда и DDoS атак"""
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.requests = defaultdict(list)
        self.max_requests = max_requests
        self.time_window = time_window
    
    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь отправить запрос"""
        now = datetime.now()
        user_requests = self.requests[user_id]
        
        # Удаляем старые запросы
        user_requests[:] = [
            req_time for req_time in user_requests
            if now - req_time < timedelta(seconds=self.time_window)
        ]
        
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        return True

# ==================== МЕНЕДЖЕРЫ ДАННЫХ ====================
class DataManager:
    """Управление данными приложения"""
    def __init__(self):
        self.users: Dict[int, Dict] = {}
        self.carts: Dict[int, Dict[int, int]] = defaultdict(dict)
        self.bookings: Dict[int, List[Dict]] = defaultdict(list)
        self.user_stats: Dict[int, Dict] = defaultdict(lambda: {
            'commands_used': 0,
            'last_active': None,
            'sessions': 0
        })
    
    def get_user_data(self, user_id: int) -> Dict:
        """Получает данные пользователя"""
        return self.users.get(user_id, {})
    
    def update_user_data(self, user_id: int, data: Dict):
        """Обновляет данные пользователя"""
        if user_id not in self.users:
            self.users[user_id] = {}
        self.users[user_id].update(data)
    
    def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        """Добавляет товар в корзину"""
        if product_id in self.carts[user_id]:
            self.carts[user_id][product_id] += quantity
        else:
            self.carts[user_id][product_id] = quantity
    
    def get_cart_total(self, user_id: int) -> float:
        """Вычисляет сумму корзины"""
        cart = self.carts.get(user_id, {})
        total = 0
        for product_id, quantity in cart.items():
            if product_id in PRODUCTS:
                total += PRODUCTS[product_id]['price'] * quantity
        return total

# ==================== ДАННЫЕ ДЛЯ ДЕМО ====================
PRODUCTS = {
    1: {"name": "📱 iPhone 15 Pro", "price": 999, "category": "Электроника", "description": "Новейший iPhone с камерой 48 Мп"},
    2: {"name": "💻 MacBook Air M3", "price": 1299, "category": "Ноутбуки", "description": "Мощный и легкий ноутбук"},
    3: {"name": "📚 Python для профи", "price": 49, "category": "Книги", "description": "Продвинутое руководство по Python"},
    4: {"name": "🎧 AirPods Pro", "price": 249, "category": "Электроника", "description": "Беспроводные наушники с шумоподавлением"},
    5: {"name": "⌚ Apple Watch", "price": 399, "category": "Гаджеты", "description": "Умные часы для здоровья и фитнеса"},
}

SERVICES = {
    1: {"name": "💇 Стрижка", "duration": "1 час", "price": 1500},
    2: {"name": "💅 Маникюр", "duration": "1.5 часа", "price": 2000},
    3: {"name": "✂️ Бритье", "duration": "30 мин", "price": 800},
    4: {"name": "🧖‍♀️ Спа-уход", "duration": "2 часа", "price": 3500},
}

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
rate_limiter = RateLimiter()
data_manager = DataManager()

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Основное меню бота"""
    keyboard = [
        [
            InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
            InlineKeyboardButton("📅 Запись", callback_data="booking")
        ],
        [
            InlineKeyboardButton("📊 Опрос", callback_data="quiz"),
            InlineKeyboardButton("💰 Курсы", callback_data="currency")
        ],
        [
            InlineKeyboardButton("ℹ️ Обо мне", callback_data="about"),
            InlineKeyboardButton("📞 Контакты", callback_data="contact")
        ]
    ]
    # Добавляем кнопку админ-панели только для админов
    if ADMIN_IDS:
        keyboard.append([
            InlineKeyboardButton("🛠️ Админ-панель", callback_data="admin")
        ])
    
    return InlineKeyboardMarkup(keyboard)

def get_shop_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура магазина"""
    categories = sorted(set(p["category"] for p in PRODUCTS.values()))
    keyboard = []
    
    for category in categories:
        keyboard.append([InlineKeyboardButton(f"📂 {category}", callback_data=f"cat_{category}")])
    
    keyboard.extend([
        [InlineKeyboardButton("🛒 Моя корзина", callback_data="cart")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ДЕКОРАТОРЫ ====================
def admin_only(func):
    """Декоратор для ограничения доступа к админ-функциям"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ У вас нет доступа к этой функции!",
                    show_alert=True
                )
            elif update.message:
                await update.message.reply_text("⛔ У вас нет доступа к этой команде!")
            return
        
        return await func(update, context)
    return wrapper

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Обновляем статистику
    data_manager.user_stats[user_id]['sessions'] += 1
    data_manager.user_stats[user_id]['last_active'] = datetime.now()
    
    # Приветственное сообщение
    welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Я - *демонстрационный бот*, созданный для показа возможностей Telegram ботов.

✨ *Что я умею:*
• 🛍️ Полноценный интернет-магазин с корзиной
• 📅 Систему бронирования услуг
• 📊 Интерактивные опросы и викторины
• 💰 Получение актуальных курсов валют
• 🛠️ Админ-панель для управления

👇 Выберите раздел ниже, чтобы увидеть возможности!
"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )
    
    logger.info(f"Новый пользователь: {user_id} - {user.username}")

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🏠 *Главное меню*",
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

# ==================== МОДУЛЬ МАГАЗИНА ====================
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открытие магазина"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🛍️ *Наш магазин*\n\nВыберите категорию товаров:",
        reply_markup=get_shop_keyboard(),
        parse_mode='Markdown'
    )

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показ товаров категории"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat_", "")
    
    # Формируем сообщение с товарами
    text = f"📂 *{category}*\n\n"
    
    keyboard = []
    for product_id, product in PRODUCTS.items():
        if product["category"] == category:
            text += f"• *{product['name']}* - ${product['price']}\n"
            text += f"  _{product['description']}_\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"➕ {product['name']} - ${product['price']}",
                    callback_data=f"add_{product_id}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="shop")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def add_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление товара в корзину"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.replace("add_", ""))
    user_id = query.from_user.id
    
    if product_id not in PRODUCTS:
        await query.message.reply_text("❌ Товар не найден!")
        return
    
    # Добавляем в корзину
    data_manager.add_to_cart(user_id, product_id)
    product = PRODUCTS[product_id]
    
    await query.message.reply_text(
        f"✅ *{product['name']}* добавлен в корзину!\n"
        f"💵 Цена: ${product['price']}",
        parse_mode='Markdown'
    )

async def view_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Просмотр корзины"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    cart = data_manager.carts.get(user_id, {})
    
    if not cart:
        await query.edit_message_text(
            "🛒 Ваша корзина пуста!",
            reply_markup=get_shop_keyboard()
        )
        return
    
    # Формируем список товаров в корзине
    text = "🛒 *Ваша корзина*\n\n"
    total = 0
    
    for product_id, quantity in cart.items():
        if product_id in PRODUCTS:
            product = PRODUCTS[product_id]
            item_total = product['price'] * quantity
            total += item_total
            
            text += f"• {product['name']}\n"
            text += f"  Кол-во: {quantity} × ${product['price']} = ${item_total}\n\n"
    
    text += f"💵 *Итого: ${total}*\n"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"),
            InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")
        ],
        [InlineKeyboardButton("🔙 Продолжить покупки", callback_data="shop")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Оформление заказа"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    
    # Получаем общую сумму
    total = data_manager.get_cart_total(user_id)
    
    if total == 0:
        await query.answer("❌ Ваша корзина пуста!", show_alert=True)
        return
    
    # Формируем заказ
    order_text = f"""
✅ *Заказ оформлен!*

👤 *Клиент:* {user_name}
💰 *Сумма заказа:* ${total}
📅 *Дата:* {datetime.now().strftime('%d.%m.%Y %H:%M')}

📞 Наш менеджер свяжется с вами в течение 15 минут для подтверждения заказа.

✨ *Это демонстрация системы интернет-магазина в Telegram!*
"""
    
    # Логируем заказ
    logger.info(f"Новый заказ: {user_id} - {user_name} - ${total}")
    
    # Очищаем корзину
    data_manager.carts[user_id] = {}
    
    await query.edit_message_text(
        order_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def clear_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистка корзины"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data_manager.carts[user_id] = {}
    
    await query.edit_message_text(
        "🗑️ Корзина очищена!",
        reply_markup=get_shop_keyboard()
    )

# ==================== МОДУЛЬ БРОНИРОВАНИЯ ====================
async def booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню бронирования"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for service_id, service in SERVICES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{service['name']} - ${service['price']} ({service['duration']})",
                callback_data=f"book_{service_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main")])
    
    await query.edit_message_text(
        "📅 *Бронирование услуг*\n\nВыберите услугу:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def book_service_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор услуги для бронирования"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.replace("book_", ""))
    service = SERVICES[service_id]
    
    # Сохраняем выбор в контексте
    context.user_data['booking_service'] = service_id
    
    # Предлагаем выбрать время (упрощенный вариант)
    times = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    
    keyboard = []
    row = []
    for i, time in enumerate(times):
        row.append(InlineKeyboardButton(time, callback_data=f"time_{time}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="booking")])
    
    await query.edit_message_text(
        f"📅 *{service['name']}*\n\n"
        f"💰 Цена: ${service['price']}\n"
        f"⏱ Длительность: {service['duration']}\n\n"
        f"Выберите удобное время:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def book_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждение бронирования"""
    query = update.callback_query
    await query.answer()
    
    time = query.data.replace("time_", "")
    service_id = context.user_data.get('booking_service')
    
    if not service_id:
        await query.edit_message_text("❌ Ошибка: услуга не выбрана")
        return
    
    service = SERVICES[service_id]
    user = query.from_user
    
    # Формируем подтверждение
    confirmation_text = f"""
✅ *Бронирование подтверждено!*

👤 *Клиент:* {user.full_name}
📋 *Услуга:* {service['name']}
⏰ *Время:* {time}
💰 *Стоимость:* ${service['price']}
⏱ *Длительность:* {service['duration']}

📞 Администратор свяжется с вами для подтверждения записи.

✨ *Это демонстрация системы бронирования в Telegram!*
"""
    
    # Логируем бронирование
    logger.info(f"Новое бронирование: {user.id} - {service['name']} - {time}")
    
    # Сохраняем бронирование
    data_manager.bookings[user.id].append({
        "service": service['name'],
        "time": time,
        "date": datetime.now().strftime('%d.%m.%Y'),
        "price": service['price']
    })
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

# ==================== МОДУЛЬ ОПРОСА ====================
async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало опроса"""
    query = update.callback_query
    await query.answer()
    
    text = """
❓ *Тест: Какой бот нужен вашему бизнесу?*

Ответьте на 3 вопроса и получите персонализированную рекомендацию!

Готовы начать?
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать тест", callback_data="quiz_start")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def quiz_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Первый вопрос опроса"""
    query = update.callback_query
    await query.answer()
    
    text = """
*Вопрос 1/3*

🎯 Какова основная цель бота для вашего бизнеса?

A) 🛍️ Продажи товаров/услуг
B) 📅 Запись клиентов
C) 👨‍💼 Поддержка клиентов
D) 📢 Информирование аудитории
"""
    
    keyboard = [
        [
            InlineKeyboardButton("A) Продажи", callback_data="quiz_a"),
            InlineKeyboardButton("B) Запись", callback_data="quiz_b")
        ],
        [
            InlineKeyboardButton("C) Поддержка", callback_data="quiz_c"),
            InlineKeyboardButton("D) Информирование", callback_data="quiz_d")
        ],
        [InlineKeyboardButton("🔙 Отмена", callback_data="main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ответа на опрос"""
    query = update.callback_query
    await query.answer()
    
    answer = query.data
    
    # Простая логика для демо
    result_text = """
🎉 *Спасибо за прохождение теста!*

📊 *На основе ваших ответов, вам подойдет:*

🤖 **Многофункциональный бот под ключ**

✨ *Рекомендуемые модули:*
• Интернет-магазин с корзиной
• Система бронирования
• CRM-интеграция
• Автоматические уведомления
• Аналитика и отчетность

💡 *Хотите получить бесплатную консультацию?*
"""
    
    keyboard = [
        [InlineKeyboardButton("📞 Получить консультацию", callback_data="contact")],
        [InlineKeyboardButton("🛠️ Заказать такой бот", callback_data="about")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main")]
    ]
    
    await query.edit_message_text(
        result_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== МОДУЛЬ КУРСОВ ВАЛЮТ ====================
async def currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Курсы валют"""
    query = update.callback_query
    await query.answer()
    
    # Демо-данные (в реальном боте используйте API)
    currency_data = {
        "USD": {"rate": 92.5, "change": "+0.5"},
        "EUR": {"rate": 100.2, "change": "+0.3"},
        "CNY": {"rate": 12.8, "change": "-0.1"},
        "GBP": {"rate": 116.7, "change": "+0.7"}
    }
    
    text = "💱 *Курсы валют к RUB*\n\n"
    
    for currency, data in currency_data.items():
        text += f"*{currency}*: {data['rate']} ₽ ({data['change']}%)\n"
    
    text += "\n📈 *Данные обновлены:* 15:30 МСК"
    text += "\n\n✨ *Демонстрация модуля финансовой информации*"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="currency")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== ИНФОРМАЦИОННЫЕ РАЗДЕЛЫ ====================
async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Информация о разработчике"""
    query = update.callback_query
    await query.answer()
    
    text = """
👨‍💻 *О разработчике*

🚀 Я специализируюсь на создании Telegram ботов под ключ для бизнеса любого масштаба.

🛠️ *Мой стек технологий:*
• Python + python-telegram-bot (асинхронный)
• PostgreSQL/Redis для хранения данных
• Docker для контейнеризации
• REST API интеграции
• Веб-хуки и long polling

🎯 *Что я предлагаю клиентам:*
1. 📊 *Анализ бизнес-процессов* - выявление точек для автоматизации
2. 🎨 *Дизайн UX/UI* - удобный интерфейс для пользователей
3. 💻 *Разработка* - чистый, поддерживаемый код
4. 🚀 *Деплой и настройка* - размещение на надежном хостинге
5. 🔧 *Поддержка* - гарантийное обслуживание

📈 *Результаты для бизнеса:*
• Снижение нагрузки на персонал до 70%
• Увеличение конверсии на 25-40%
• Круглосуточная доступность сервиса
• Сбор ценной аналитики о клиентах

"""
    
    keyboard = [
        [InlineKeyboardButton("📞 Связаться", callback_data="contact")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Контакты"""
    query = update.callback_query
    await query.answer()
    
    text = """
📞 *Контакты для связи*

💬 *Telegram:* @GrigoryShag
📧 *Email:* gregoryshaginyan@yandex.ru

🕐 *Время работы:*
Пн-Пт: 9:00-18:00
Сб-Вс: по договоренности

💡 *Порядок работы:*
1. Бесплатная консультация (30 мин)
2. Составление ТЗ и оценка
3. Разработка прототипа
4. Полная реализация
5. Тестирование и запуск
6. Техническая поддержка

⏱️ *Средние сроки разработки:*
• Простой бот: 3-5 дней
• Средней сложности: 1-2 недели
• Сложный проект: 3-4 недели

💰 *Стоимость:* от 15.000 ₽
"""
    
    keyboard = [
        [
            InlineKeyboardButton("💬 Написать в Telegram", url="https://t.me/@GrigoryShag"),
            InlineKeyboardButton("📧 Отправить email", url="gregoryshaginyan@yandex.ru")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== АДМИН-ПАНЕЛЬ ====================
@admin_only
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ-панель"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🛠️ *Административная панель*",
        reply_markup=get_admin_keyboard(),
        parse_mode='Markdown'
    )

@admin_only
async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика бота"""
    query = update.callback_query
    await query.answer()
    
    total_users = len(data_manager.users)
    active_carts = len([c for c in data_manager.carts.values() if c])
    total_bookings = sum(len(b) for b in data_manager.bookings.values())
    
    # Считаем активных пользователей (последние 7 дней)
    week_ago = datetime.now() - timedelta(days=7)
    active_users = sum(
        1 for stats in data_manager.user_stats.values()
        if stats['last_active'] and stats['last_active'] > week_ago
    )
    
    text = f"""
📊 *Статистика бота*

👥 *Всего пользователей:* {total_users}
🟢 *Активных (7 дней):* {active_users}
🛒 *Активных корзин:* {active_carts}
📅 *Всего бронирований:* {total_bookings}

📈 *Активность за сегодня:*
• Команд: {sum(stats['commands_used'] for stats in data_manager.user_stats.values())}
• Сессий: {sum(stats['sessions'] for stats in data_manager.user_stats.values())}

🕐 *Обновлено:* {datetime.now().strftime('%H:%M:%S')}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 В админку", callback_data="admin")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== ОБРАБОТЧИК ОШИБОК ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    error_message = "⚠️ Произошла непредвиденная ошибка. Мы уже работаем над ее исправлением!"
    
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_message
            )
        except Exception:
            pass

# ==================== ЗАПУСК БОТА ====================
def main() -> None:
    """Запуск бота"""
    try:
        # Создаем Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        
        # Добавляем обработчики callback'ов
        application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main$"))
        application.add_handler(CallbackQueryHandler(shop_callback, pattern="^shop$"))
        application.add_handler(CallbackQueryHandler(booking_callback, pattern="^booking$"))
        application.add_handler(CallbackQueryHandler(quiz_callback, pattern="^quiz$"))
        application.add_handler(CallbackQueryHandler(currency_callback, pattern="^currency$"))
        application.add_handler(CallbackQueryHandler(about_callback, pattern="^about$"))
        application.add_handler(CallbackQueryHandler(contact_callback, pattern="^contact$"))
        application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin$"))
        application.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
        
        # Магазин
        application.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
        application.add_handler(CallbackQueryHandler(add_to_cart_callback, pattern="^add_"))
        application.add_handler(CallbackQueryHandler(view_cart_callback, pattern="^cart$"))
        application.add_handler(CallbackQueryHandler(checkout_callback, pattern="^checkout$"))
        application.add_handler(CallbackQueryHandler(clear_cart_callback, pattern="^clear_cart$"))
        
        # Бронирование
        application.add_handler(CallbackQueryHandler(book_service_callback, pattern="^book_"))
        application.add_handler(CallbackQueryHandler(book_time_callback, pattern="^time_"))
        
        # Опрос
        application.add_handler(CallbackQueryHandler(quiz_start_callback, pattern="^quiz_start$"))
        application.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern="^quiz_[a-d]$"))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        print("=" * 50)
        print("🤖 Telegram Bot Demo запускается...")
        print(f"👤 Админы: {ADMIN_IDS}")
        print("=" * 50)
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
