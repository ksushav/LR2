

import sqlite3
import os
import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'Tanya.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

# Создание таблиц при запуске бота
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            telegram_id INTEGER,
            role INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            callback_data TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Токен вашего бота
TOKEN = '7498886179:AAGacTqOZAX2TuriXNjPzkpangIA5XTLnXs'  # Замените на ваш токен

# Список слов и подсказок для игры
words = ["кошка", "собака", "машина", "дерево", "река", "дом", "цветок", "стол", "книга"]
hints = {
    "кошка": "Это домашнее животное, часто ловит мышей.",
    "собака": "Верный друг человека.",
    "машина": "Транспортное средство на колесах.",
    "дерево": "Это растет в лесу и в парках.",
    "река": "Течет и впадает в море или океан.",
    "дом": "Место, где люди живут.",
    "цветок": "Красивый и часто пахучий элемент растений.",
    "стол": "Мебель для работы или еды.",
    "книга": "Многостраничный объект для чтения."
}

# Асинхронный обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user.id,))
    user_record = cursor.fetchone()
    if not user_record:
        await update.message.reply_text(
            'Привет! Для начала регистрации используйте команду /register. Введите ваш уникальный Telegram ID и имя пользователя через пробел.\nПример: `/register 12345678 Tanya`',
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text('Добро пожаловать обратно!')

    # Логирование команды
    log_command(user.id, '/start')
    conn.close()

# Асинхронный обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Доступные команды:\n'
        '/start - начало работы\n'
        '/help - помощь\n'
        '/fact - получить факт о воде\n'
        '/play - начать игру в слова\n'
        '/register - регистрация\n'
        '/stop - остановить игру'
    )
    # Логирование команды
    log_command(update.effective_user.id, '/help')

# Асинхронный обработчик команды /fact
async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    facts = [
        "Вода составляет примерно 71% поверхности Земли.",
        "Около 1/6 всего объема воды содержится в ледяных шапках и ледниках.",
        "Вода в жидком состоянии является фазой, в которой водные молекулы соединены водородными связями."
    ]
    random_fact = random.choice(facts)
    await update.message.reply_text(f"Вот интересный факт о воде: {random_fact}")
    # Логирование команды
    log_command(update.effective_user.id, '/fact')

# Асинхронный обработчик команды /play
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    word = random.choice(words)
    context.user_data['play'] = {
        'word': word,
        'hints_used': 0
    }
    await update.message.reply_text("Я загадал слово, попробуй угадать его! Чтобы завершить игру, напишите /stop.")
    # Логирование команды
    log_command(update.effective_user.id, '/play')

# Асинхронный обработчик команды /stop
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'play' in context.user_data:
        del context.user_data['play']
        await update.message.reply_text("Игра была остановлена. Спасибо за игру!")
        # Логирование команды
        log_command(update.effective_user.id, '/stop')
    else:
        await update.message.reply_text("У вас нет активной игры.")

# Асинхронный обработчик регистрации
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        args = context.args
        if len(args) != 2:
            raise ValueError
        telegram_id, username = args
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (telegram_id, username))
        conn.commit()
        conn.close()
        await update.message.reply_text(f'Вы успешно зарегистрированы как {username} с Telegram ID {telegram_id}.')
        # Логирование команды
        log_command(user.id, '/register')
    except ValueError:
        await update.message.reply_text('Пожалуйста, используйте правильный формат: /register <Telegram ID> <Имя пользователя>')
    except sqlite3.IntegrityError:
        await update.message.reply_text('Пользователь с таким Telegram ID уже зарегистрирован.')
    except Exception as e:
        await update.message.reply_text(f'Ошибка при регистрации: {e}')

# Асинхронный обработчик сообщений для игры
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'play' in context.user_data:
        user_guess = update.message.text.strip().lower()
        game_data = context.user_data['play']
        correct_word = game_data['word']
        if user_guess == '/stop':
            await update.message.reply_text("Игра была остановлена. Спасибо за игру!")
            del context.user_data['play']
            # Логирование команды
            log_command(update.effective_user.id, '/stop')
        elif user_guess == correct_word:
            await update.message.reply_text(f"Да! Ты угадал слово: {correct_word}. Поздравляю!")
            del context.user_data['play']
            # Логирование команды
            log_command(update.effective_user.id, user_guess)
        else:
            game_data['hints_used'] += 1
            if game_data['hints_used'] == 1:
                hint = hints.get(correct_word, "Без подсказки.")
                await update.message.reply_text(f"Нет, не угадал. Вот подсказка: {hint}")
            else:
                await update.message.reply_text("Нет, не угадал. Попробуй еще раз! Или напиши /stop")
            # Логирование попытки
            log_command(update.effective_user.id, user_guess)
    else:
        await update.message.reply_text("Неизвестная команда. Используйте /help для списка доступных команд.")

def log_command(user_telegram_id, command):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE telegram_id = ?", (user_telegram_id,))
    user = cursor.fetchone()
    if user:
        user_id = user['user_id']
        date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO command_usage (user_id, command, date) VALUES (?, ?, ?)", (user_id, command, date))
        conn.commit()
    conn.close()

# Асинхронный обработчик нажатий на inline-кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    command = query.data
    if command == 'fact':
        await fact(query, context)
    elif command == 'help':
        await help_command(query, context)
    elif command == 'play':
        await play(query, context)
    elif command == 'register':
        await register_command(update, context)
    else:
        await query.edit_message_text(f'Вы вызвали команду: {command}')
    # Логирование команды
    log_command(update.effective_user.id, command)

# Функция добавления пользовательских кнопок из базы данных
async def start_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT text, callback_data FROM bot_buttons")
    buttons = cursor.fetchall()
    keyboard = [
        [InlineKeyboardButton("Факты", callback_data='fact')],
        [InlineKeyboardButton("Помощь", callback_data='help')],
        [InlineKeyboardButton("Игра", callback_data='play')],
        [InlineKeyboardButton("Регистрация", callback_data='register')],
    ]
    for button in buttons:
        keyboard.append([InlineKeyboardButton(button['text'], callback_data=button['callback_data'])])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Привет! Я должен служить тебе. Выберите опцию:', reply_markup=reply_markup)
    # Логирование команды
    log_command(update.effective_user.id, '/start')

# Основная функция для запуска бота
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_buttons))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fact", fact))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()



if __name__ == '__main__':
    main()