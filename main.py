# ✅ Telegram TaskBot v2.1 — Полноценный бот для задач с проектами, дедлайнами и интерактивным управлением

import os
import sqlite3
import threading
import time
from datetime import datetime
import telebot
from telebot import types

TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

# Таблица с задачами
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    is_done INTEGER DEFAULT 0,
    remind_at TEXT,
    deadline TEXT,
    project TEXT DEFAULT 'Общий'
)''')
conn.commit()

user_states = {}
user_temp_data = {}
current_project_filter = {}  # user_id -> project

# === Вспомогательные функции ===
def send_task_list(chat_id):
    project = current_project_filter.get(chat_id, 'Общий')
    cursor.execute("SELECT id, text, is_done, deadline FROM tasks WHERE user_id=? AND project=? ORDER BY \
                   CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (chat_id, project))
    tasks = cursor.fetchall()
    if not tasks:
        bot.send_message(chat_id, f"📁 Проект: {project}\nНет задач.")
        return
    response = [f"📁 Проект: {project}\n"]
    for idx, (task_id, text, is_done, deadline) in enumerate(tasks, 1):
        status = "✅ " if is_done else ""
        deadline_str = f" (⏰ {datetime.fromisoformat(deadline).strftime('%d.%m.%Y %H:%M')})" if deadline else ""
        response.append(f"{status}{idx}. {text}{deadline_str}")
    bot.send_message(chat_id, "\n".join(response))

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/add', '/list')
    markup.row('/done', '/undone', '/delete')
    markup.row('/project', '/setproject')
    bot.send_message(message.chat.id, "Привет! Я TaskBot — бот для задач с проектами, дедлайнами и напоминаниями.", reply_markup=markup)
    current_project_filter[message.chat.id] = 'Общий'
    send_task_list(message.chat.id)

# === /project — выбрать активный проект ===
@bot.message_handler(commands=['project'])
def switch_project(message):
    bot.send_message(message.chat.id, "🔁 Введи название проекта, задачи которого хочешь видеть:")
    user_states[message.chat.id] = 'set_project_filter'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'set_project_filter')
def set_project_filter(message):
    current_project_filter[message.chat.id] = message.text.strip()
    user_states.pop(message.chat.id)
    bot.send_message(message.chat.id, f"✅ Проект установлен: {message.text.strip()}")
    send_task_list(message.chat.id)

# === /add ===
@bot.message_handler(commands=['add'])
def add_task(message):
    bot.send_message(message.chat.id, "✍️ Введи задачи (через ; или с новой строки):")
    user_states[message.chat.id] = 'awaiting_task_text'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_task_text')
def receive_tasks(message):
    tasks = [t.strip() for t in message.text.replace('\n', ';').split(';') if t.strip()]
    user_temp_data[message.chat.id] = {'tasks': tasks}
    bot.send_message(message.chat.id, "🗂 В какой проект добавить задачи?")
    user_states[message.chat.id] = 'awaiting_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_project')
def receive_project(message):
    user_temp_data[message.chat.id]['project'] = message.text.strip()
    bot.send_message(message.chat.id, "📆 Укажи дедлайн (ДД.ММ.ГГГГ ЧЧ:ММ) или напиши -")
    user_states[message.chat.id] = 'awaiting_deadline'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_deadline')
def receive_deadline(message):
    data = user_temp_data.pop(message.chat.id, {})
    deadline_input = message.text.strip()
    try:
        deadline = None if deadline_input == '-' else datetime.strptime(deadline_input, "%d.%m.%Y %H:%M").isoformat()
    except:
        bot.send_message(message.chat.id, "⚠️ Неверный формат. Используй ДД.ММ.ГГГГ ЧЧ:ММ или -")
        return
    for t in data['tasks']:
        cursor.execute("INSERT INTO tasks (user_id, text, project, deadline) VALUES (?, ?, ?, ?)",
                       (message.chat.id, t, data['project'], deadline))
    conn.commit()
    current_project_filter[message.chat.id] = data['project']
    user_states.pop(message.chat.id)
    bot.send_message(message.chat.id, "✅ Задачи добавлены!")
    send_task_list(message.chat.id)

# === /done ===
@bot.message_handler(commands=['done'])
def start_done(message):
    bot.send_message(message.chat.id, "☑️ Введи номера задач для отметки как выполненные (через пробел):")
    user_states[message.chat.id] = 'awaiting_done'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_done')
def mark_done(message):
    nums = list(map(int, message.text.strip().split()))
    project = current_project_filter.get(message.chat.id, 'Общий')
    cursor.execute("SELECT id FROM tasks WHERE user_id=? AND project=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id, project))
    task_ids = [row[0] for row in cursor.fetchall()]
    for n in nums:
        if 1 <= n <= len(task_ids):
            cursor.execute("UPDATE tasks SET is_done=1 WHERE id=?", (task_ids[n-1],))
    conn.commit()
    user_states.pop(message.chat.id)
    send_task_list(message.chat.id)

# === /undone ===
@bot.message_handler(commands=['undone'])
def start_undone(message):
    bot.send_message(message.chat.id, "🔄 Введи номера задач для возврата в активные:")
    user_states[message.chat.id] = 'awaiting_undone'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_undone')
def mark_undone(message):
    nums = list(map(int, message.text.strip().split()))
    project = current_project_filter.get(message.chat.id, 'Общий')
    cursor.execute("SELECT id FROM tasks WHERE user_id=? AND project=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id, project))
    task_ids = [row[0] for row in cursor.fetchall()]
    for n in nums:
        if 1 <= n <= len(task_ids):
            cursor.execute("UPDATE tasks SET is_done=0 WHERE id=?", (task_ids[n-1],))
    conn.commit()
    user_states.pop(message.chat.id)
    send_task_list(message.chat.id)

# === /delete ===
@bot.message_handler(commands=['delete'])
def start_delete(message):
    bot.send_message(message.chat.id, "🗑 Введи номера задач для удаления:")
    user_states[message.chat.id] = 'awaiting_delete'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_delete')
def delete_tasks(message):
    nums = list(map(int, message.text.strip().split()))
    project = current_project_filter.get(message.chat.id, 'Общий')
    cursor.execute("SELECT id FROM tasks WHERE user_id=? AND project=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id, project))
    task_ids = [row[0] for row in cursor.fetchall()]
    for n in nums:
        if 1 <= n <= len(task_ids):
            cursor.execute("DELETE FROM tasks WHERE id=?", (task_ids[n-1],))
    conn.commit()
    user_states.pop(message.chat.id)
    send_task_list(message.chat.id)

# === Напоминания по времени ===
def reminder_loop():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("SELECT id, user_id, text FROM tasks WHERE remind_at IS NOT NULL AND remind_at <= ?", (now,))
        for t in cursor.fetchall():
            bot.send_message(t[1], f"🔔 Напоминание:\n{t[2]}")
            cursor.execute("UPDATE tasks SET remind_at=NULL WHERE id=?", (t[0],))
        conn.commit()
        time.sleep(30)

threading.Thread(target=reminder_loop, daemon=True).start()
bot.polling()
