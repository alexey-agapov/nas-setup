import os
import logging
import asyncio
import json
from collections import deque
from dotenv import load_dotenv
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from functools import wraps
from typing import Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path
import shutil

from yt_dlp_agent import YouTubeDLAgent  # your agent class

# Load .env variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = {233251607}  # Replace with your Telegram user IDs

DOWNLOAD_DIR = Path( os.getenv( "DOWNLOAD_DIR"))
TARGET_DIR = Path( os.environ.get( "PLEX_LIBRARY_ROOT"))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER")
LLM_API_KEY = os.environ.get("LLM_API_KEY")

# Download control
MAX_CONCURRENT_DOWNLOADS = 2
active_downloads: Dict[str, Dict] = {}  # url -> {"task": Task, "status": {}}
download_queue = deque()
yt_agent = YouTubeDLAgent( download_dir=DOWNLOAD_DIR)
 
@dataclass
class DownloadContext:
    url: str
    user_id: int
    bot: any
    status: Dict = field(default_factory=lambda: {"step": None, "status": None, "progress": {}, "filename": None, "classification": None, "final_path": None})
    metadata: Optional[Dict] = None
    download_path: Optional[str] = None
    final_path: Optional[str] = None
    classification: Optional[str] = None
    error: Optional[str] = None

# Restrict to allowed users
def restricted(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            await update.message.reply_text("⛔ Access denied.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# Start command
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! Send me a video URL to start the download.")

# Handle text messages (URLs)
@restricted
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    status_msg = await update.message.reply_text(f"🔍 Checking if I can download this link")

    if not yt_agent.can_handle(url):
        await status_msg.edit_text("❌ Sorry, I cannot download this link. Please send a supported video URL.")
        return

    if len(active_downloads) < MAX_CONCURRENT_DOWNLOADS:
        await status_msg.edit_text("✅ Download has started.")
        await start_workflow(url, user_id, context, status_msg)
    else:
        await status_msg.edit_text("⏳ Download will start soon—waiting for other downloads to finish.")
        download_queue.append((url, user_id, status_msg))

# Start a workflow task and track it
async def start_workflow(url: str, user_id: int, context: ContextTypes.DEFAULT_TYPE, status_msg: Message):
    dl_context = DownloadContext(
        url=url,
        user_id=user_id,
        bot=context.bot,
    )

    task = context.application.create_task(execute_pipeline(dl_context))
    active_downloads[url] = {"task": task, "status": dl_context}
    task.add_done_callback(lambda t: download_done(context, url))

# Workflow steps
def _new_status_msg(text: str, context: DownloadContext):
    return context.bot.send_message(chat_id=context.user_id, text=text)

def load_metadata(downloaded_video: Path) -> dict:
    json_file = downloaded_video.with_suffix(".info.json")
    if not json_file.exists():
        raise FileNotFoundError("Metadata JSON not found.")
    with open(json_file, "r", encoding="utf-8") as f:
        full_metadata = json.load(f)
    metadata = {
        "title": full_metadata.get("title"),
        "uploader": full_metadata.get("uploader"),
        "description": full_metadata.get("description"),
        "duration_string": full_metadata.get("duration_string"),
        "tags": full_metadata.get("tags", []),
        "upload_date": full_metadata.get("upload_date"),
    }
    print("[+] Loaded reduced metadata from JSON.")
    return metadata

async def step_download(context: DownloadContext):
    context.status["step"] = "download"
    context.status["status"] = "in_progress"
    status_msg = await _new_status_msg("⬇️ Step 1: Downloading video...", context)
    loop = asyncio.get_event_loop()

    def hook(d):
        context.status["status"] = d["status"]
        context.status["filename"] = d.get("filename")
        context.status["progress"] = {
            "downloaded": d.get("downloaded_bytes", 0),
            "total": d.get("total_bytes", 0),
            "eta": d.get("eta")
        }
        
        # Construct a simple progress string
        downloaded = context.status["progress"]["downloaded"]
        total = context.status["progress"]["total"]
        eta = context.status["progress"]["eta"]
        msg = f"⬇️ Downloading...\n{downloaded / 1e6:.1f} MB / {total / 1e6:.1f} MB\nETA: {eta}s"

        # Schedule the status message update
        #status_msg.edit_text(msg)

    def blocking_download():
        context.status["filename"] = yt_agent.download(context.url, hook)

    await loop.run_in_executor(None, blocking_download)
    context.download_path = context.status["filename"]
    context.metadata = load_metadata( context.download_path)
    context.status["status"] = "completed"
    await status_msg.edit_text("✅ Download completed.")

async def step_classify(context: DownloadContext):
    context.status["step"] = "classify"
    context.status["status"] = "in_progress"
    status_msg = await _new_status_msg("🧠 Step 2: Classifying content...", context)

    try:
        categories = [name for name in os.listdir(TARGET_DIR) if os.path.isdir(os.path.join(TARGET_DIR, name))]
        category_list = ", ".join(categories)

        system_prompt = (
            "You are a media librarian assistant. Your job is to classify videos "
            f"into one of the existing library categories: {category_list}. These categories correspond "
            "to folders in the media library and are intended to group similar types of content together.\n\n"

            "Based on available information (such as title, uploader, description, duration, and tags), "
            "select the most appropriate existing category. If none of the existing categories reasonably fits, "
            "you may introduce a new category, but only under the following strict conditions:\n"
            "- The content is significantly different from all existing categories.\n"
            "- The new category must be general enough to accommodate future similar content (not one-off).\n"
            "- Prefer existing categories whenever possible to avoid fragmentation.\n\n"

            "In addition, generate a suggested filename suitable for organizing this video within the chosen category. "
            "The filename should reflect the title, uploader, and date (if available), and be formatted appropriately "
            "for the target category.\n\n"

            "Return a JSON object like this:\n"
            "{\"category\": str, \"suggested_filename\": str}"
            )

        metadata = context.metadata
        user_prompt = (
            f"Title: {metadata.get('title')}\n"
            f"Uploader: {metadata.get('uploader')}\n"
            f"Description: {metadata.get('description')}\n"
            f"Duration: {metadata.get('duration_string')}\n"
            f"Tags: {', '.join(metadata.get('tags', []))}\n\n"
            "Return valid JSON of the following structure: {\"category\": str, \"suggested_filename\": str}"
        )

        if LLM_PROVIDER == "openai":
            import openai
            client = openai.OpenAI(api_key=LLM_API_KEY)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            content = response.choices[0].message.content

        elif LLM_PROVIDER == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=LLM_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")

            response = model.generate_content(
                contents=f"{system_prompt}\n\n{user_prompt}",
                generation_config={"response_mime_type": "application/json"}
            )
            content = response.text

        else:
            raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

        classification = json.loads(content)
        context.classification = classification["category"]
        context.status["classification"] = context.classification
        context.status["suggested_filename"] = classification["suggested_filename"]
        context.status["status"] = "completed"

        await status_msg.edit_text(f"✅ Classified as: {context.classification}")

    except Exception as e:
        context.status["status"] = "error"
        raise e

async def step_finalize(context: DownloadContext):
    context.status["step"] = "finalize"
    context.status["status"] = "in_progress"
    status_msg = await _new_status_msg("📦 Step 3: Moving file to final destination...", context)
    if context.download_path and context.classification:
        final_dir = TARGET_DIR / Path( context.classification)
        os.makedirs(final_dir, exist_ok=True)
        final_path = final_dir / Path( context.status["suggested_filename"])
        shutil.move(context.download_path, final_path)
        context.final_path = final_path
        context.status["final_path"] = final_path
        context.status["status"] = "completed"
        await status_msg.edit_text(f"✅ File moved to: {final_path}")
    else:
        context.status["status"] = "error"
        raise Exception("Missing download path or classification")
    
# Pipeline executor
async def execute_pipeline(context: DownloadContext):
    STEPS = [
        step_download,
        step_classify,
        step_finalize,
    ]

    for step in STEPS:
        try:
            await step(context)
        except Exception as e:
            context.error = str(e)
            await context.bot.send_message(
                chat_id=context.user_id,
                text=f"❌ Workflow failed at {step.__name__}: {e}"
            )
            return

    await context.bot.send_message(
        chat_id=context.user_id,
        text=f"✅ Workflow complete. File moved to: {context.final_path}"
    )

# When a download finishes, check queue
def download_done(context: ContextTypes.DEFAULT_TYPE, completed_url: str):
    if completed_url in active_downloads:
        del active_downloads[completed_url]

    if download_queue and len(active_downloads) < MAX_CONCURRENT_DOWNLOADS:
        url, user_id, status_msg = download_queue.popleft()
        context.application.create_task(start_workflow(url, user_id, context, status_msg))

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
