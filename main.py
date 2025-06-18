# ✅ Полный Telegram TaskBot v1.1 (с поддержкой множественных операций и статистикой)

import os
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot import types

TOKEN = os.environ.get('BOT_TOKEN') or 'ВАШ_ТОКЕН_ОТСЮДА'
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

# --- Общая функция показа задач ---
def send_task_list(chat_id):
    cursor.execute("SELECT id, text, is_done, deadline, project, completed_at, priority FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (chat_id,))
    tasks = cursor.fetchall()
    now = datetime.now()
    result, idx, projects = [], 1, {}
    for t in tasks:
        id, text, is_done, deadline, project, completed_at, priority = t
        if is_done and completed_at and datetime.fromisoformat(completed_at) + timedelta(hours=24) < now:
            continue
        if project not in projects: projects[project] = []
        status = "✅ " if is_done else ""
        prio = f" {priority}" if priority else ""
        deadline_str = f" (⏳ до {datetime.fromisoformat(deadline).strftime('%d.%m.%Y')})" if deadline else ""
        projects[project].append(f"{status}{idx}. {text}{prio}{deadline_str}")
        idx += 1
    for project, lines in projects.items():
        result.append(f"📁 Проект: {project}")
        result.extend(lines)
        result.append("")
    bot.send_message(chat_id, "\n".join(result) if result else "📭 Нет активных задач.")

# --- Команды ---
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row('/add', '/list', '/edit')
    kb.row('/done', '/undone', '/delete')
    kb.row('/project', '/history', '/stats')
    bot.send_message(msg.chat.id, "Привет! Я TaskBot. Веди свои задачи легко ✨", reply_markup=kb)
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['list'])
def cmd_list(msg):
    send_task_list(msg.chat.id)

# --- Множественное добавление ---
@bot.message_handler(commands=['add'])
def cmd_add(msg):
    bot.send_message(msg.chat.id, "📝 Введи задачи через `;` или с новой строки:")
    user_states[msg.chat.id] = 'add_text'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_text')
def step_project(msg):
    raw = msg.text.strip().replace('\n', ';')
    user_temp_data[msg.chat.id] = {'tasks': [x.strip() for x in raw.split(';') if x.strip()]}
    bot.send_message(msg.chat.id, "📁 Проект (или -):")
    user_states[msg.chat.id] = 'add_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_project')
def step_deadline(msg):
    user_temp_data[msg.chat.id]['project'] = msg.text.strip() if msg.text.strip() != '-' else 'Общий'
    bot.send_message(msg.chat.id, "📆 Дедлайн (ДД.ММ.ГГГГ) или -:")
    user_states[msg.chat.id] = 'add_deadline'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_deadline')
def step_priorities(msg):
    try:
        deadline = None if msg.text.strip() == '-' else datetime.strptime(msg.text.strip(), "%d.%m.%Y").date().isoformat()
        user_temp_data[msg.chat.id]['deadline'] = deadline
        lines = [f"{i+1}. {t}" for i, t in enumerate(user_temp_data[msg.chat.id]['tasks'])]
        bot.send_message(msg.chat.id, "🔻 Отправь приоритеты для задач по порядку (🔴/🟡/🟢/-), через пробел\nПример: 🔴 🟡 🔴")
        bot.send_message(msg.chat.id, "\n".join(lines))
        user_states[msg.chat.id] = 'add_priorities'
    except:
        bot.send_message(msg.chat.id, "Неверный формат даты. Попробуй ещё раз")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_priorities')
def finalize_add(msg):
    prios = msg.text.strip().split()
    temp = user_temp_data.pop(msg.chat.id)
    for i, text in enumerate(temp['tasks']):
        prio = prios[i] if i < len(prios) and prios[i] in ['🔴', '🟡', '🟢'] else None
        cursor.execute("INSERT INTO tasks (user_id, text, project, deadline, priority) VALUES (?, ?, ?, ?, ?)",
                       (msg.chat.id, text, temp['project'], temp['deadline'], prio))
    conn.commit()
    user_states.pop(msg.chat.id, None)
    bot.send_message(msg.chat.id, "✅ Все задачи добавлены!")
    send_task_list(msg.chat.id)

# --- Множественные команды (done, delete и др.) ---
def get_task_ids_by_numbers(chat_id, nums):
    cursor.execute("SELECT id FROM tasks WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline", (chat_id,))
    task_ids = cursor.fetchall()
    return [task_ids[n-1][0] for n in nums if 0 < n <= len(task_ids)]

@bot.message_handler(commands=['done'])
def cmd_done(msg):
    bot.send_message(msg.chat.id, "✅ Введи номера задач для отметки (через пробел):")
    user_states[msg.chat.id] = 'mark_done'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'mark_done')
def mark_done(msg):
    try:
        nums = list(map(int, msg.text.strip().split()))
        for tid in get_task_ids_by_numbers(msg.chat.id, nums):
            cursor.execute("UPDATE tasks SET is_done=1, completed_at=? WHERE id=?", (datetime.now().isoformat(), tid))
        conn.commit()
    except:
        bot.send_message(msg.chat.id, "Ошибка! Проверь номера.")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['delete'])
def cmd_delete(msg):
    bot.send_message(msg.chat.id, "🗑 Введи номера задач для удаления:")
    user_states[msg.chat.id] = 'delete_task'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'delete_task')
def do_delete(msg):
    try:
        nums = list(map(int, msg.text.strip().split()))
        for tid in get_task_ids_by_numbers(msg.chat.id, nums):
            cursor.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit()
    except:
        bot.send_message(msg.chat.id, "Ошибка! Проверь номера.")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

# --- История и статистика ---
@bot.message_handler(commands=['history'])
def cmd_history(msg):
    cursor.execute("SELECT text, completed_at, project FROM tasks WHERE user_id=? AND is_done=1 ORDER BY completed_at DESC", (msg.chat.id,))
    rows = cursor.fetchall()
    result = [f"✅ [{p}] {t} ({datetime.fromisoformat(c).strftime('%d.%m.%Y')})" for t, c, p in rows]
    bot.send_message(msg.chat.id, "\n".join(result) or "Нет завершённых задач.")

@bot.message_handler(commands=['stats'])
def cmd_stats(msg):
    uid = msg.chat.id
    cursor.execute("SELECT project, COUNT(*) FROM tasks WHERE user_id=?", (uid,))
    all_ = dict(cursor.fetchall())
    cursor.execute("SELECT project, COUNT(*) FROM tasks WHERE user_id=? AND is_done=1", (uid,))
    done = dict(cursor.fetchall())
    lines = [f"📁 {p}: {done.get(p, 0)}/{all_[p]} ({int(done.get(p, 0)/all_[p]*100)}%)" for p in all_]
    bot.send_message(uid, "📊 Прогресс по проектам:\n\n" + "\n".join(lines))

bot.polling()
