# ✅ Полный Telegram TaskBot v1.0 (финальная версия, всё в одном)

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
    result, visible, idx, projects = [], [], 1, {}
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

@bot.message_handler(commands=['add'])
def cmd_add(msg):
    bot.send_message(msg.chat.id, "📝 Введи текст задачи:")
    user_states[msg.chat.id] = 'add_text'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_text')
def step_project(msg):
    user_temp_data[msg.chat.id] = {'text': msg.text.strip()}
    bot.send_message(msg.chat.id, "📁 Проект задачи (или -):")
    user_states[msg.chat.id] = 'add_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_project')
def step_deadline(msg):
    user_temp_data[msg.chat.id]['project'] = msg.text.strip() if msg.text != '-' else 'Общий'
    bot.send_message(msg.chat.id, "📆 Дедлайн (ДД.ММ.ГГГГ) или -:")
    user_states[msg.chat.id] = 'add_deadline'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_deadline')
def step_priority(msg):
    try:
        deadline = None if msg.text.strip() == '-' else datetime.strptime(msg.text.strip(), "%d.%m.%Y").date().isoformat()
        user_temp_data[msg.chat.id]['deadline'] = deadline
        bot.send_message(msg.chat.id, "🔻 Приоритет (🔴 / 🟡 / 🟢 / -):")
        user_states[msg.chat.id] = 'add_priority'
    except:
        bot.send_message(msg.chat.id, "Неверный формат даты. Попробуй снова")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'add_priority')
def step_save(msg):
    prio = msg.text.strip()
    if prio not in ['🔴', '🟡', '🟢']: prio = None
    temp = user_temp_data.pop(msg.chat.id, {})
    cursor.execute("INSERT INTO tasks (user_id, text, project, deadline, priority) VALUES (?, ?, ?, ?, ?)", (msg.chat.id, temp['text'], temp['project'], temp['deadline'], prio))
    conn.commit()
    user_states.pop(msg.chat.id, None)
    bot.send_message(msg.chat.id, "✅ Добавлено!")
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['done'])
def cmd_done(msg):
    bot.send_message(msg.chat.id, "✅ Номер задачи для отметки как выполненной:")
    user_states[msg.chat.id] = 'mark_done'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'mark_done')
def mark_done(msg):
    try:
        num = int(msg.text.strip())
        tid = cursor.execute("SELECT id FROM tasks WHERE user_id=?", (msg.chat.id,)).fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET is_done=1, completed_at=? WHERE id=?", (datetime.now().isoformat(), tid))
        conn.commit()
    except: bot.send_message(msg.chat.id, "Ошибка! Проверь номер.")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['undone'])
def cmd_undone(msg):
    bot.send_message(msg.chat.id, "↩️ Номер задачи для возврата в активные:")
    user_states[msg.chat.id] = 'mark_undone'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'mark_undone')
def mark_undone(msg):
    try:
        num = int(msg.text.strip())
        tid = cursor.execute("SELECT id FROM tasks WHERE user_id=?", (msg.chat.id,)).fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET is_done=0, completed_at=NULL WHERE id=?", (tid,))
        conn.commit()
    except: bot.send_message(msg.chat.id, "Ошибка!")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['delete'])
def cmd_delete(msg):
    bot.send_message(msg.chat.id, "🗑 Номер задачи для удаления:")
    user_states[msg.chat.id] = 'delete_task'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'delete_task')
def do_delete(msg):
    try:
        num = int(msg.text.strip())
        tid = cursor.execute("SELECT id FROM tasks WHERE user_id=?", (msg.chat.id,)).fetchall()[num-1][0]
        cursor.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit()
    except: bot.send_message(msg.chat.id, "Ошибка!")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

@bot.message_handler(commands=['edit'])
def cmd_edit(msg):
    bot.send_message(msg.chat.id, "✏️ Введи номер задачи для изменения:")
    user_states[msg.chat.id] = 'edit_choose'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'edit_choose')
def edit_choice(msg):
    try:
        user_temp_data[msg.chat.id] = {'num': int(msg.text.strip())}
        bot.send_message(msg.chat.id, "Что изменить?\n1 — текст\n2 — приоритет\n3 — дедлайн\n4 — всё сразу")
        user_states[msg.chat.id] = 'edit_mode'
    except: bot.send_message(msg.chat.id, "Ошибка в номере.")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'edit_mode')
def edit_mode(msg):
    mode = msg.text.strip()
    uid = msg.chat.id
    if mode == '1': bot.send_message(uid, "✏️ Новый текст:"); user_states[uid] = 'edit_text'
    elif mode == '2': bot.send_message(uid, "🔻 Новый приоритет (🔴/🟡/🟢/-):"); user_states[uid] = 'edit_priority'
    elif mode == '3': bot.send_message(uid, "📆 Новый дедлайн (ДД.ММ.ГГГГ или -):"); user_states[uid] = 'edit_deadline'
    elif mode == '4': bot.send_message(uid, "✏️ Новый текст:"); user_states[uid] = 'edit_all_text'
    else: bot.send_message(uid, "Ошибка в выборе.")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, '').startswith('edit'))
def handle_edit_steps(msg):
    uid = msg.chat.id
    num = user_temp_data[uid]['num']
    tid = cursor.execute("SELECT id FROM tasks WHERE user_id=?", (uid,)).fetchall()[num-1][0]
    state = user_states[uid]
    if state == 'edit_text':
        cursor.execute("UPDATE tasks SET text=? WHERE id=?", (msg.text.strip(), tid))
    elif state == 'edit_priority':
        prio = msg.text.strip()
        prio = None if prio == '-' else prio
        cursor.execute("UPDATE tasks SET priority=? WHERE id=?", (prio, tid))
    elif state == 'edit_deadline':
        dline = None if msg.text.strip() == '-' else datetime.strptime(msg.text.strip(), "%d.%m.%Y").date().isoformat()
        cursor.execute("UPDATE tasks SET deadline=? WHERE id=?", (dline, tid))
    elif state == 'edit_all_text':
        cursor.execute("UPDATE tasks SET text=? WHERE id=?", (msg.text.strip(), tid))
        bot.send_message(uid, "📆 Новый дедлайн (ДД.ММ.ГГГГ или -):")
        user_states[uid] = 'edit_all_deadline'
        return
    elif state == 'edit_all_deadline':
        dline = None if msg.text.strip() == '-' else datetime.strptime(msg.text.strip(), "%d.%m.%Y").date().isoformat()
        cursor.execute("UPDATE tasks SET deadline=? WHERE id=?", (dline, tid))
        bot.send_message(uid, "🔻 Приоритет (🔴/🟡/🟢/-):")
        user_states[uid] = 'edit_all_priority'
        return
    elif state == 'edit_all_priority':
        prio = msg.text.strip()
        prio = None if prio == '-' else prio
        cursor.execute("UPDATE tasks SET priority=? WHERE id=?", (prio, tid))
    conn.commit()
    user_states.pop(uid, None)
    user_temp_data.pop(uid, None)
    bot.send_message(uid, "✅ Обновлено!")
    send_task_list(uid)

@bot.message_handler(commands=['project'])
def cmd_project(msg):
    bot.send_message(msg.chat.id, "🔀 Укажи номер задачи и новое название проекта:")
    user_states[msg.chat.id] = 'change_project'

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'change_project')
def change_project(msg):
    try:
        parts = msg.text.strip().split()
        num, new_proj = int(parts[0]), ' '.join(parts[1:]) or 'Общий'
        tid = cursor.execute("SELECT id FROM tasks WHERE user_id=?", (msg.chat.id,)).fetchall()[num-1][0]
        cursor.execute("UPDATE tasks SET project=? WHERE id=?", (new_proj, tid))
        conn.commit()
        bot.send_message(msg.chat.id, "Проект обновлён ✅")
    except:
        bot.send_message(msg.chat.id, "⚠️ Ошибка. Пример: 3 Личное")
    user_states.pop(msg.chat.id, None)
    send_task_list(msg.chat.id)

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
