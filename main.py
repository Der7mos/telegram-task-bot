import os
import telebot
import sqlite3
import threading
import time
from telebot import types

# Получаем токен из переменной окружения
TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
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

# Приветствие и кнопки
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/add', '/list')
    markup.row('/delete', '/remind')
    bot.send_message(message.chat.id,
        "Привет! Я — твой личный таск-бот ✅\n\nВот что я умею:\n"
        "/add — добавить одну или несколько задач\n"
        "/list — список задач\n"
        "/delete — удалить задачи по ID\n"
        "/remind — поставить напоминание",
        reply_markup=markup
    )

# Добавление одной или нескольких задач
@bot.message_handler(commands=['add'])
def add_task(message):
    task_text = message.text[5:].strip()
    if not task_text:
        bot.send_message(message.chat.id, "Используй:\n/add Задача 1; Задача 2\nили\n/add\nЗадача 1\nЗадача 2")
        return
    tasks = [t.strip() for t in task_text.replace('\n', ';').split(';') if t.strip()]
    for task in tasks:
        cursor.execute("INSERT INTO tasks (user_id, text, remind_at) VALUES (?, ?, ?)",
                       (message.chat.id, task, None))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ Добавлены задачи:\n• " + "\n• ".join(tasks))

# Список задач
@bot.message_handler(commands=['list'])
def list_tasks(message):
    cursor.execute("SELECT id, text FROM tasks WHERE user_id=?", (message.chat.id,))
    tasks = cursor.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "У тебя нет задач.")
    else:
        response = "\n".join([f"{task[0]}. {task[1]}" for task in tasks])
        bot.send_message(message.chat.id, response)

# Удаление нескольких задач
@bot.message_handler(commands=['delete'])
def delete_tasks(message):
    try:
        ids = list(map(int, message.text.split()[1:]))
        for task_id in ids:
            cursor.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, f"🗑️ Удалены задачи: {', '.join(map(str, ids))}")
    except:
        bot.send_message(message.chat.id, "Используй: /delete ID1 ID2 ...")

# Напоминания по нескольким задачам
@bot.message_handler(commands=['remind'])
def remind_tasks(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            raise Exception("Недостаточно аргументов")
        delay_minutes = int(parts[-1])
        ids = list(map(int, parts[1:-1]))
        remind_time = int(time.time()) + delay_minutes * 60
        for task_id in ids:
            cursor.execute("UPDATE tasks SET remind_at=? WHERE id=? AND user_id=?",
                           (remind_time, task_id, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, f"⏰ Напоминание через {delay_minutes} мин для задач: {', '.join(map(str, ids))}")
    except:
        bot.send_message(message.chat.id, "Формат: /remind ID1 ID2 ... минуты")

# Фоновая проверка напоминаний
def reminder_loop():
    while True:
        now = int(time.time())
        cursor.execute("SELECT id, user_id, text FROM tasks WHERE remind_at IS NOT NULL AND remind_at <= ?", (now,))
        tasks = cursor.fetchall()
        for task in tasks:
            bot.send_message(task[1], f"⏰ Напоминание: {task[2]}")
            cursor.execute("UPDATE tasks SET remind_at=NULL WHERE id=?", (task[0],))
        conn.commit()
        time.sleep(30)

# Запуск
threading.Thread(target=reminder_loop, daemon=True).start()
bot.polling()
