
import os
import io
import base64
import asyncio
import logging
from datetime import datetime, timezone

from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

IMAGE_MODEL = "gpt-image-2.5-flare"
DAILY_LIMIT = 3

# Temporary storage. We will add a database later.
usage = {}
history = {}
last_prompts = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def can_generate(user_id):
    today = datetime.now(timezone.utc).date().isoformat()
    key = (user_id, today)
    return usage.get(key, 0) < DAILY_LIMIT, key


async def generate_image(update, context, prompt):
    user = update.effective_user
    chat = update.effective_chat

    if not prompt or len(prompt) > 1500:
        await update.message.reply_text(
            "Please send a description between 1 and 1500 characters."
        )
        return

    allowed, usage_key = can_generate(user.id)

    if not allowed:
        await update.message.reply_text(
            f"You've reached your daily limit of {DAILY_LIMIT} images. "
            "Please try again tomorrow."
        )
        return

    # Reserve a generation slot before calling the paid API.
    usage[usage_key] = usage.get(usage_key, 0) + 1

    status = await update.message.reply_text(
        "🎨 Fushi is creating your image. Please wait..."
    )

    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action=ChatAction.UPLOAD_PHOTO,
        )

        # Run the synchronous image API call without blocking Telegram.
        result = await asyncio.to_thread(
            client.images.generate,
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            n=1,
        )

        image_data = base64.b64decode(result.data[0].b64_json)
        image_file = io.BytesIO(image_data)
        image_file.name = "fushi-creation.png"

        await update.message.reply_photo(
            photo=image_file,
            caption="✨ Created with Fushi AI",
        )

        history.setdefault(user.id, []).append(prompt)
        history[user.id] = history[user.id][-10:]
        last_prompts[user.id] = prompt

        await status.delete()

    except Exception:
        # Give the user their reserved slot back if generation fails.
        usage[usage_key] = max(0, usage.get(usage_key, 1) - 1)
        logger.exception("Image generation failed")
        await status.edit_text(
            "Sorry, Fushi couldn't create that image. "
            "Please try again later."
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Fushi AI!\n\n"
        "Your personal AI creative studio.\n\n"
        "Describe any image you want and I'll create it.\n\n"
        "Try /create followed by your idea.\n"
        "You get 3 image generations per day during our beta."
    )


async def help_command(update, context):
    await update.message.reply_text(
        "🎨 FUSHI AI COMMANDS\n\n"
        "/create - Generate an image\n"
        "/meme - Create a meme\n"
        "/anime - Create anime artwork\n"
        "/crypto - Create Web3 artwork\n"
        "/nft - Create NFT artwork\n"
        "/pfp - Create a profile picture\n"
        "/variations - Recreate your last prompt\n"
        "/history - View your recent prompts\n"
        "/style - See available art styles\n"
        "/help - Show this help message\n\n"
        "You can also send me an image description directly."
    )


async def create_command(update, context):
    prompt = " ".join(context.args)
    await generate_image(update, context, prompt)


async def preset_command(update, context):
    command = update.message.text.split()[0].split("@")[0].lower()
    description = " ".join(context.args)

    presets = {
        "/meme": "Create a funny, polished internet meme: ",
        "/anime": "Create detailed anime-style artwork: ",
        "/crypto": "Create professional Web3 and crypto-themed artwork: ",
        "/nft": "Create original collectible NFT-style artwork: ",
        "/pfp": "Create a striking square profile picture: ",
    }

    if not description:
        await update.message.reply_text(
            f"Add a description after {command}."
        )
        return

    await generate_image(
        update,
        context,
        presets[command] + description,
    )


async def variations(update, context):
    prompt = last_prompts.get(update.effective_user.id)

    if not prompt:
        await update.message.reply_text(
            "Create an image first, then use /variations."
        )
        return

    await generate_image(
        update,
        context,
        prompt + ". Create a fresh variation with a different composition.",
    )


async def history_command(update, context):
    prompts = history.get(update.effective_user.id, [])

    if not prompts:
        await update.message.reply_text("You haven't created any images yet.")
        return

    message = "🗂 Your recent prompts:\n\n"
    for number, prompt in enumerate(prompts, 1):
        message += f"{number}. {prompt[:180]}\n\n"

    await update.message.reply_text(message[:4000])


async def style_command(update, context):
    await update.message.reply_text(
        "🎨 Fushi art styles:\n\n"
        "Anime • 3D • Cartoon • Realistic • Pixel art\n"
        "Cyberpunk • Minimalist • Cinematic • Comic book\n\n"
        "Use /create and include the style in your description."
    )


async def text_prompt(update, context):
    await generate_image(
        update,
        context,
        update.message.text,
    )


async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("create", create_command))
    app.add_handler(CommandHandler("meme", preset_command))
    app.add_handler(CommandHandler("anime", preset_command))
    app.add_handler(CommandHandler("crypto", preset_command))
    app.add_handler(CommandHandler("nft", preset_command))
    app.add_handler(CommandHandler("pfp", preset_command))
    app.add_handler(CommandHandler("variations", variations))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("style", style_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_prompt,
        )
    )

    logger.info("Fushi AI is starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep the application running.
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
