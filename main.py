import os
import telebot
import sqlite3
import threading
import time

# Получаем токен из переменной окружения Railway
TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(TOKEN)

# Создаем (или подключаемся к) SQLite-базе
conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    remind_at INTEGER
)''')
conn.commit()

# Команда: /add <текст задачи>
@bot.message_handler(commands=['add'])
def add_task(message):
    task_text = message.text[5:].strip()
    if not task_text:
        bot.send_message(message.chat.id, "Используй: /add задача")
        return
    cursor.execute("INSERT INTO tasks (user_id, text, remind_at) VALUES (?, ?, ?)",
                   (message.chat.id, task_text, None))
    conn.commit()
    bot.send_message(message.chat.id, "Задача добавлена!")

# Команда: /list
@bot.message_handler(commands=['list'])
def list_tasks(message):
    cursor.execute("SELECT id, text FROM tasks WHERE user_id=?", (message.chat.id,))
    tasks = cursor.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "У тебя нет задач.")
    else:
        response = "\n".join([f"{task[0]}. {task[1]}" for task in tasks])
        bot.send_message(message.chat.id, response)

# Команда: /delete <id>
@bot.message_handler(commands=['delete'])
def delete_task(message):
    try:
        task_id = int(message.text.split()[1])
        cursor.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, "Удалено.")
    except:
        bot.send_message(message.chat.id, "Используй: /delete ID")

# Команда: /remind <id> <минуты>
@bot.message_handler(commands=['remind'])
def remind_task(message):
    try:
        parts = message.text.split()
        task_id = int(parts[1])
        delay_minutes = int(parts[2])
        remind_time = int(time.time()) + delay_minutes * 60
        cursor.execute("UPDATE tasks SET remind_at=? WHERE id=? AND user_id=?", 
                       (remind_time, task_id, message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, f"Напоминание через {delay_minutes} мин.")
    except:
        bot.send_message(message.chat.id, "Формат: /remind ID минуты")

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

threading.Thread(target=reminder_loop, daemon=True).start()

# Запуск бота
bot.polling()
