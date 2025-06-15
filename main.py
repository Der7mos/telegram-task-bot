from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
tasks = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот задач. Напиши /добавить чтобы начать.")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if not task:
        await update.message.reply_text("Укажи задачу после команды.")
        return
    tasks.append(task)
    await update.message.reply_text(f"Добавлена задача: {task}")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("На сегодня задач нет!")
    else:
        await update.message.reply_text("\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks)))

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("добавить", add))
app.add_handler(CommandHandler("сегодня", today))

if __name__ == "__main__":
    app.run_polling()
