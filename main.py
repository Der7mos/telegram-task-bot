# ✅ Telegram TaskBot v3.3 — Полноценный интерактивный таск-менеджер

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
    markup.row('/priority', '/deadline', '/project')
    markup.row('/history', '/stats')
    bot.send_message(message.chat.id, "Привет! Я TaskBot v3.3 — твой помощник ✨", reply_markup=markup)
    current_project_filter[message.chat.id] = 'Общий'
    send_task_list(message.chat.id)

@bot.message_handler(commands=['list'])
def list_tasks(message):
    send_task_list(message.chat.id)

@bot.message_handler(commands=['done'])
def done(message):
    bot.send_message(message.chat.id, "✅ Укажи номер задачи, которую выполнил:")
    user_states[message.chat.id] = 'mark_done'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'mark_done')
def mark_done_step(message):
    try:
        num = int(message.text.strip())
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET is_done=1, completed_at=? WHERE id=?", (datetime.now().isoformat(), task_id))
        conn.commit()
        bot.send_message(message.chat.id, "Задача отмечена как выполненная ✅")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Проверь номер.")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

@bot.message_handler(commands=['undone'])
def undone(message):
    bot.send_message(message.chat.id, "↩️ Укажи номер задачи для возврата в активные:")
    user_states[message.chat.id] = 'mark_undone'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'mark_undone')
def mark_undone_step(message):
    try:
        num = int(message.text.strip())
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET is_done=0, completed_at=NULL WHERE id=?", (task_id,))
        conn.commit()
        bot.send_message(message.chat.id, "Задача восстановлена в список")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Проверь номер.")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

@bot.message_handler(commands=['delete'])
def delete(message):
    bot.send_message(message.chat.id, "🗑 Укажи номер задачи, которую удалить:")
    user_states[message.chat.id] = 'delete_task'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'delete_task')
def delete_task(message):
    try:
        num = int(message.text.strip())
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
        bot.send_message(message.chat.id, "Удалено 🗑")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Проверь номер.")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

@bot.message_handler(commands=['priority'])
def ask_priority(message):
    bot.send_message(message.chat.id, "🔻 Укажи номер задачи и смайлик приоритета (🔴/🟡/🟢/-):")
    user_states[message.chat.id] = 'change_priority'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'change_priority')
def change_priority(message):
    try:
        parts = message.text.strip().split()
        num = int(parts[0])
        prio = parts[1]
        priority = prio if prio in ['🔴', '🟡', '🟢'] else None
        if prio == '-': priority = None
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET priority=? WHERE id=?", (priority, task_id))
        conn.commit()
        bot.send_message(message.chat.id, "Приоритет обновлён 🔻")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Укажи правильно: номер и приоритет")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

@bot.message_handler(commands=['deadline'])
def ask_deadline(message):
    bot.send_message(message.chat.id, "📆 Укажи номер задачи и дедлайн (ДД.ММ.ГГГГ) или -:")
    user_states[message.chat.id] = 'change_deadline'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'change_deadline')
def change_deadline(message):
    try:
        parts = message.text.strip().split()
        num = int(parts[0])
        date_input = parts[1]
        deadline = None if date_input == '-' else datetime.strptime(date_input, "%d.%m.%Y").date().isoformat()
        cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (message.chat.id,))
        task_id = cursor.fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET deadline=? WHERE id=?", (deadline, task_id))
        conn.commit()
        bot.send_message(message.chat.id, "Дедлайн обновлён 📆")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Формат: номер и дата")
    user_states.pop(message.chat.id, None)
    send_task_list(message.chat.id)

@bot.message_handler(commands=['history'])
def show_history(message):
    cursor.execute("SELECT text, completed_at, project FROM tasks WHERE user_id=? AND is_done=1 ORDER BY completed_at DESC", (message.chat.id,))
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "📭 Нет завершённых задач.")
        return
    result = []
    for text, completed, project in rows:
        completed_str = datetime.fromisoformat(completed).strftime('%d.%m.%Y')
        result.append(f"✅ [{project}] {text} ({completed_str})")
    bot.send_message(message.chat.id, "\n".join(result))

@bot.message_handler(commands=['stats'])
def show_stats(message):
    cursor.execute("SELECT project, COUNT(*) FROM tasks WHERE user_id=? GROUP BY project", (message.chat.id,))
    all_projects = dict(cursor.fetchall())
    cursor.execute("SELECT project, COUNT(*) FROM tasks WHERE user_id=? AND is_done=1 GROUP BY project", (message.chat.id,))
    done_projects = dict(cursor.fetchall())
    result = []
    for proj in all_projects:
        total = all_projects.get(proj, 0)
        done = done_projects.get(proj, 0)
        percent = int((done / total) * 100) if total else 0
        result.append(f"📁 {proj}: {done}/{total} задач выполнено ({percent}%)")
    bot.send_message(message.chat.id, "📊 Статистика по проектам:\n\n" + "\n".join(result))

# Точка входа
bot.polling()
