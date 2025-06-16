import os
import sqlite3
import threading
import time
import telebot
from datetime import datetime
from telebot import types

# === Настройки ===
TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)
conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

# === База данных ===
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    is_done INTEGER DEFAULT 0,
    remind_at TEXT
)
''')
conn.commit()

# === Состояния пользователей ===
user_states = {}

# === /start ===
@bot.message_handler(commands=['start'])
def welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/add', '/list')
    markup.row('/delete', '/done', '/undone')
    markup.row('/remind')
    bot.send_message(message.chat.id,
        "👋 Привет! Я твой TaskBot.\n\nЧто я умею:\n"
        "✅ Добавлять задачи (/add)\n"
        "📋 Показывать задачи (/list)\n"
        "🗑 Удалять задачи (/delete)\n"
        "☑️ Отмечать выполненные (/done)\n"
        "🔁 Возвращать обратно (/undone)\n"
        "⏰ Напоминать в нужное время (/remind)",
        reply_markup=markup
    )

# === Интерактивное добавление ===
@bot.message_handler(commands=['add'])
def start_add(message):
    user_states[message.chat.id] = 'awaiting_tasks'
    bot.send_message(message.chat.id,
        "✍️ Введи список задач (через `;` или с новой строки):")

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == 'awaiting_tasks')
def receive_tasks(message):
    raw = message.text.replace('\n', ';')
    tasks = [t.strip() for t in raw.split(';') if t.strip()]
    for t in tasks:
        cursor.execute("INSERT INTO tasks (user_id, text) VALUES (?, ?)", (message.chat.id, t))
    conn.commit()
    user_states.pop(message.chat.id)
    bot.send_message(message.chat.id, f"✅ Добавлены задачи:\n• " + "\n• ".join(tasks))

# === Список задач ===
@bot.message_handler(commands=['list'])
def show_tasks(message):
    cursor.execute("SELECT id, text, is_done, remind_at FROM tasks WHERE user_id=?", (message.chat.id,))
    tasks = cursor.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "🟡 У тебя пока нет задач.")
        return
    lines = []
    for t in tasks:
        status = "✅" if t[2] else "⬜️"
        reminder = f" ⏰ {t[3]}" if t[3] else ""
        lines.append(f"{status} {t[0]}. {t[1]}{reminder}")
    bot.send_message(message.chat.id, "\n".join(lines))

# === Удаление задач ===
@bot.message_handler(commands=['delete'])
def delete_tasks(message):
    try:
        ids = list(map(int, message.text.split()[1:]))
        for i in ids:
            cursor.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (i, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, f"🗑 Удалены: {', '.join(map(str, ids))}")
    except:
        bot.send_message(message.chat.id, "Используй: /delete 1 2 3")

# === Выполнено / Невыполнено ===
@bot.message_handler(commands=['done'])
def mark_done(message):
    ids = list(map(int, message.text.split()[1:]))
    for i in ids:
        cursor.execute("UPDATE tasks SET is_done=1 WHERE id=? AND user_id=?", (i, message.chat.id))
    conn.commit()
    bot.send_message(message.chat.id, f"☑️ Отмечены как выполненные: {', '.join(map(str, ids))}")

@bot.message_handler(commands=['undone'])
def mark_undone(message):
    ids = list(map(int, message.text.split()[1:]))
    for i in ids:
        cursor.execute("UPDATE tasks SET is_done=0 WHERE id=? AND user_id=?", (i, message.chat.id))
    conn.commit()
    bot.send_message(message.chat.id, f"🔄 Вернули в список: {', '.join(map(str, ids))}")

# === Напоминание ===
@bot.message_handler(commands=['remind'])
def set_reminder(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            raise ValueError
        ids = list(map(int, parts[1:-1]))
        dt = datetime.strptime(parts[-1], "%d.%m.%Y_%H:%M")  # формат: 16.06.2025_18:30
        for i in ids:
            cursor.execute("UPDATE tasks SET remind_at=? WHERE id=? AND user_id=?", (dt.isoformat(), i, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, f"⏰ Напоминания установлены на {dt.strftime('%d.%m.%Y %H:%M')} для задач: {', '.join(map(str, ids))}")
    except:
        bot.send_message(message.chat.id, "Используй формат: /remind 1 2 3 16.06.2025_18:30")

# === Фоновый напоминатель ===
def reminder_loop():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("SELECT id, user_id, text FROM tasks WHERE remind_at IS NOT NULL AND remind_at <= ?", (now,))
        tasks = cursor.fetchall()
        for t in tasks:
            bot.send_message(t[1], f"🔔 Напоминание:\n{t[2]}")
            cursor.execute("UPDATE tasks SET remind_at=NULL WHERE id=?", (t[0],))
        conn.commit()
        time.sleep(30)

threading.Thread(target=reminder_loop, daemon=True).start()
bot.polling()
