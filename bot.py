
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

# ---------------- CONFIGURATION ----------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

IMAGE_MODEL = os.getenv(
    "OPENAI_IMAGE_MODEL",
    "gpt-image-2.5-flare"
)

DAILY_LIMIT = 3

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    raise RuntimeError(
        "Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY"
    )

client = OpenAI(
    api_key=OPENAI_KEY,
    timeout=180.0,
    max_retries=1
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger("FushiAI")

usage = {}
history = {}
last_prompts = {}


# ---------------- DAILY LIMIT ----------------

def get_usage_key(user_id):
    today = datetime.now(timezone.utc).date().isoformat()
    return (user_id, today)


# ---------------- IMAGE GENERATION ----------------

async def generate_image(update, context, prompt):

    if not prompt or not prompt.strip():
        await update.message.reply_text(
            "Please describe the image you want Fushi to create."
        )
        return

    prompt = prompt.strip()

    if len(prompt) > 1500:
        await update.message.reply_text(
            "Your description is too long. Please keep it under 1500 characters."
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    usage_key = get_usage_key(user_id)

    if usage.get(usage_key, 0) >= DAILY_LIMIT:
        await update.message.reply_text(
            f"You have used your {DAILY_LIMIT} daily image generations. "
            "Please try again tomorrow."
        )
        return

    # Reserve one generation while the request runs.
    usage[usage_key] = usage.get(usage_key, 0) + 1

    status = await update.message.reply_text(
        "🎨 Fushi is creating your artwork. Please wait..."
    )

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_PHOTO
        )

        # Call OpenAI without blocking Telegram.
        result = await asyncio.to_thread(
            client.images.generate,
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            n=1
        )

        if not result.data or not result.data[0].b64_json:
            raise RuntimeError(
                "The image API returned no image data."
            )

        image_bytes = base64.b64decode(
            result.data[0].b64_json
        )

        image_file = io.BytesIO(image_bytes)
        image_file.name = "fushi-creation.png"

        await update.message.reply_photo(
            photo=image_file,
            caption="✨ Created with Fushi AI"
        )

        history.setdefault(user_id, []).append(prompt)
        history[user_id] = history[user_id][-10:]
        last_prompts[user_id] = prompt

        # Successful generation.
        try:
            await status.delete()
        except Exception:
            pass

    except Exception as exc:

        # Return the reserved generation.
        usage[usage_key] = max(
            0, usage.get(usage_key, 1) - 1
        )

        logger.exception("IMAGE GENERATION FAILED")

        logger.error(
            "IMAGE_ERROR: %s: %s",
            type(exc).__name__,
            str(exc)[:500]
        )

        await status.edit_text(
            "❌ Fushi couldn't create your image.\n\n"
            f"Error type: {type(exc).__name__}\n"
            "Please check the server logs."
        )


# ---------------- START ----------------

async def start(update, context):

    await update.message.reply_text(
        "👋 Welcome to Fushi AI!\n\n"
        "Your personal AI creative studio.\n\n"
        "Create amazing:\n"
        "🎨 Memes\n"
        "🌌 Anime artwork\n"
        "💎 Crypto graphics\n"
        "🖼 NFT artwork\n"
        "👤 Profile pictures\n\n"
        "Send a description or use /create.\n\n"
        "You get 3 image generations daily during beta.\n\n"
        "Use /help to see all commands."
    )


# ---------------- HELP ----------------

async def help_command(update, context):

    await update.message.reply_text(
        "🎨 FUSHI AI COMMANDS\n\n"
        "/create - Generate any image\n"
        "/meme - Create a meme\n"
        "/anime - Create anime artwork\n"
        "/crypto - Create Web3 artwork\n"
        "/nft - Create NFT artwork\n"
        "/pfp - Create a profile picture\n"
        "/variations - Create a variation\n"
        "/history - View recent prompts\n"
        "/style - View art styles\n"
        "/help - Show commands\n\n"
        "You can also send an image description directly."
    )


# ---------------- CREATE ----------------

async def create_command(update, context):

    prompt = " ".join(context.args)

    await generate_image(update, context, prompt)


# ---------------- PRESET COMMANDS ----------------

async def preset_command(update, context):

    command = (
        update.message.text.split()[0]
        .split("@")[0]
        .lower()
    )

    description = " ".join(context.args)

    presets = {
        "/meme": "Create a funny, high-quality internet meme: ",
        "/anime": "Create beautiful detailed anime artwork: ",
        "/crypto": "Create professional Web3 and crypto artwork: ",
        "/nft": "Create original collectible NFT artwork: ",
        "/pfp": "Create a striking square profile picture: "
    }

    if not description:
        await update.message.reply_text(
            f"Please add a description after {command}."
        )
        return

    await generate_image(
        update,
        context,
        presets[command] + description
    )


# ---------------- VARIATIONS ----------------

async def variations(update, context):

    user_id = update.effective_user.id
    prompt = last_prompts.get(user_id)

    if not prompt:
        await update.message.reply_text(
            "Create an image first before using /variations."
        )
        return

    await generate_image(
        update,
        context,
        prompt + ". Create a fresh variation with a different composition."
    )


# ---------------- HISTORY ----------------

async def history_command(update, context):

    prompts = history.get(update.effective_user.id, [])

    if not prompts:
        await update.message.reply_text(
            "You haven't created any images yet."
        )
        return

    message = "🗂 YOUR RECENT PROMPTS\n\n"

    for number, prompt in enumerate(prompts, 1):
        message += f"{number}. {prompt[:180]}\n\n"

    await update.message.reply_text(message[:4000])


# ---------------- STYLES ----------------

async def style_command(update, context):

    await update.message.reply_text(
        "🎨 FUSHI ART STYLES\n\n"
        "Anime • 3D • Cartoon • Realistic\n"
        "Cyberpunk • Pixel art • Cinematic\n"
        "Comic book • Minimalist • Fantasy\n\n"
        "Use /create and include your preferred style."
    )


# ---------------- NORMAL TEXT ----------------

async def text_prompt(update, context):

    await generate_image(
        update,
        context,
        update.message.text
    )


# ---------------- START BOT ----------------

def main():

    app = Application.builder().token(
        TELEGRAM_TOKEN
    ).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("create", create_command))

    for command in [
        "meme", "anime", "crypto", "nft", "pfp"
    ]:
        app.add_handler(
            CommandHandler(command, preset_command)
        )

    app.add_handler(
        CommandHandler("variations", variations)
    )

    app.add_handler(
        CommandHandler("history", history_command)
    )

    app.add_handler(
        CommandHandler("style", style_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_prompt
        )
    )

    logger.info("Fushi AI is starting...")

    app.run_polling()


if __name__ == "__main__":
    main()
      
