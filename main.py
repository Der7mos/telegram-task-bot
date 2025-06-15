from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
tasks = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I’m your task bot.\nUse /add to create a task.")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if not task:
        await update.message.reply_text("❗ Please enter a task after /add")
        return
    tasks.append(task)
    await update.message.reply_text(f"✅ Task added: {task}")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("🎉 No tasks for today!")
    else:
        message = "📝 Tasks:\n" + "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
        await update.message.reply_text(message)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("today", today))

if __name__ == "__main__":
    app.run_polling()
