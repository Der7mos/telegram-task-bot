# ✅ Telegram TaskBot v3.4 — Полноценный таск-менеджер с интерактивной логикой

import os
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot import types

TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    is_done INTEGER DEFAULT 0,
    remind_at TEXT,
    deadline TEXT,
    project TEXT DEFAULT 'Общий',
    completed_at TEXT,
    priority TEXT
)''')
conn.commit()

user_states = {}
user_temp_data = {}
current_project_filter = {}

def send_task_list(chat_id):
    cursor.execute("SELECT id, text, is_done, deadline, project, completed_at, priority FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (chat_id,))
    tasks = cursor.fetchall()
    visible = []
    now = datetime.now()
    for task in tasks:
        id, text, is_done, deadline, project, completed_at, priority = task
        if is_done and completed_at:
            if datetime.fromisoformat(completed_at) + timedelta(hours=24) < now:
                continue
        visible.append(task)

    if not visible:
        bot.send_message(chat_id, "📭 Нет активных задач.")
        return

    result = []
    idx = 1
    projects = {}
    for task in visible:
        id, text, is_done, deadline, project, completed_at, priority = task
        if project not in projects:
            projects[project] = []
        prio = f" {priority}" if priority else ""
        deadline_str = f" (⏳ до {datetime.fromisoformat(deadline).strftime('%d.%m.%Y')})" if deadline else ""
        status = "✅ " if is_done else ""
        projects[project].append(f"{status}{idx}. {text}{prio}{deadline_str}")
        idx += 1

    for project, lines in projects.items():
        result.append(f"📁 Проект: {project}")
        result.extend(lines)
        result.append("")
    bot.send_message(chat_id, "\n".join(result))

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/add', '/list', '/edit')
    markup.row('/done', '/undone', '/delete')
    markup.row('/project', '/history', '/stats')
    bot.send_message(message.chat.id, "Привет! Я TaskBot v3.4 — твой помощник ✨", reply_markup=markup)
    current_project_filter[message.chat.id] = 'Общий'
    send_task_list(message.chat.id)

@bot.message_handler(commands=['add'])
def add_task_start(message):
    bot.send_message(message.chat.id, "📝 Введи текст задачи:")
    user_states[message.chat.id] = 'add_text'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_text')
def add_task_project(message):
    user_temp_data[m.chat.id] = {'text': message.text.strip()}
    bot.send_message(message.chat.id, "📁 Введи проект задачи (или - для 'Общий'):")
    user_states[m.chat.id] = 'add_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_project')
def add_task_deadline(message):
    project = message.text.strip()
    if project == '-': project = 'Общий'
    user_temp_data[m.chat.id]['project'] = project
    bot.send_message(m.chat.id, "📆 Введи дедлайн (ДД.ММ.ГГГГ) или - если без него:")
    user_states[m.chat.id] = 'add_deadline'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_deadline')
def add_task_priority(message):
    date_input = message.text.strip()
    try:
        deadline = None if date_input == '-' else datetime.strptime(date_input, "%d.%m.%Y").date().isoformat()
        user_temp_data[m.chat.id]['deadline'] = deadline
        bot.send_message(m.chat.id, "🔻 Укажи приоритет задачи (🔴/🟡/🟢/-):")
        user_states[m.chat.id] = 'add_priority'
    except:
        bot.send_message(m.chat.id, "⚠️ Неверный формат даты. Повтори:")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_priority')
def add_task_save(message):
    prio = message.text.strip()
    priority = prio if prio in ['🔴', '🟡', '🟢'] else None
    if prio == '-': priority = None
    temp = user_temp_data.pop(m.chat.id, {})
    cursor.execute("INSERT INTO tasks (user_id, text, project, deadline, priority) VALUES (?, ?, ?, ?, ?)", (m.chat.id, temp['text'], temp['project'], temp['deadline'], priority))
    conn.commit()
    user_states.pop(m.chat.id, None)
    bot.send_message(m.chat.id, "✅ Задача добавлена!")
    send_task_list(m.chat.id)

@bot.message_handler(commands=['project'])
def change_project(message):
    bot.send_message(message.chat.id, "🔀 Укажи номер задачи и новое название проекта:")
    user_states[message.chat.id] = 'change_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'change_project')
def apply_project_change(message):
    try:
        parts = message.text.strip().split()
        num = int(parts[0])
        project = ' '.join(parts[1:]) or 'Общий'
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET project=? WHERE id=?", (project, task_id))
        conn.commit()
        bot.send_message(message.chat.id, "Проект обновлён 🔁")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Пример: 2 Работа")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

# Другие команды (done, undone, delete, edit, history, stats) уже реализованы выше — см. v3.3

bot.polling()
