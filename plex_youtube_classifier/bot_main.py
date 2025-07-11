import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from functools import wraps

from yt_dlp_agent import YouTubeDLAgent  # your agent class

# Load .env variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = {233251607}  # Replace with your Telegram user IDs

def restricted(func):
    @wraps( func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            await update.message.reply_text("⛔ Access denied.")
            return
        return func(update, context, *args, **kwargs)
    return wrapper

# /start command
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Initialize your agent
yt_agent = YouTubeDLAgent()


# /start command
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! Send me a video URL to start the download.")


# Handle any text message as a potential URL
@restricted
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user = update.effective_user.first_name

    await update.message.reply_text(f"🔍 Checking if I can download: {url}")

    if yt_agent.can_handle(url):
        await update.message.reply_text("✅ This link is supported! Downloading will be implemented soon.")
    else:
        await update.message.reply_text("❌ Sorry, I cannot download this link. Please send a supported video URL.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
