import os
import telebot
import sqlite3
import threading
import time
from telebot import types

# Получаем токен из Railway переменной окружения
TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

# База данных SQLite
conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    remind_at INTEGER
)
''')
conn.commit()

# Отслеживание состояния пользователя
user_states = {}

# /start — клавиатура и описание
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/add', '/list')
    markup.row('/delete', '/remind')
    bot.send_message(message.chat.id,
        "Привет! Я — твой личный таск-бот ✅\n\nВот что я умею:\n"
        "/add — добавление задач\n"
        "/list — список задач\n"
        "/delete — удалить задачи по ID\n"
        "/remind — поставить напоминание",
        reply_markup=markup
    )

# /add — запускаем интерактивный режим
@bot.message_handler(commands=['add'])
def start_add_tasks(message):
    user_states[message.chat.id] = 'awaiting_tasks'
    bot.send_message(message.chat.id,
        "✍️ Введи список задач:\n— Через `;` или с новой строки\n— Отправь одним сообщением"
    )

# Прием задач в интерактивном режиме
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_tasks')
def receive_tasks(message):
    raw_text = message.text.strip()
    if not raw_text:
        bot.send_me_
