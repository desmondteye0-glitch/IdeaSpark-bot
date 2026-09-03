import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import google.generativeai as genai

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.5-flash")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_state = {}

PLATFORM_PROMPTS = {
    "tiktok": (
        "Generate 5 TikTok content ideas about '{topic}'. "
        "For each idea give: a scroll-stopping hook (first line of the video), "
        "a one-sentence concept, and a suggested format (e.g. talking head, "
        "voiceover + b-roll, POV, before/after). Keep it punchy, under 15 seconds "
        "of concept each. Number them 1-5."
    ),
    "instagram": (
        "Generate 5 Instagram content ideas about '{topic}'. "
        "For each idea give: a caption hook, whether it works better as a "
        "single image, carousel, or Reel, and a one-sentence visual concept. "
        "Number them 1-5."
    ),
    "youtube": (
        "Generate 5 YouTube video ideas about '{topic}'. "
        "For each idea give: a clickable title (under 60 characters), "
        "a one-sentence angle/hook for the first 10 seconds, and whether it "
        "fits better as a Short or long-form video. Number them 1-5."
    ),
}

PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "youtube": "YouTube",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=key)]
        for key, label in PLATFORM_LABELS.items()
    ]
    await update.message.reply_text(
        "Pick a platform to get content ideas for:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def platform_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data
    user_state[query.from_user.id] = {"platform": platform}
    await query.edit_message_text(
        f"{PLATFORM_LABELS[platform]} selected.\n\n"
        f"Send me a topic or niche (e.g. skincare for men, personal finance, "
        f"my dogs daily life) and I will generate ideas. "
        f"Or just send surprise me."
    )


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if not state or "platform" not in state:
        await update.message.reply_text(
            "Use /start first to pick a platform (TikTok, Instagram, or YouTube)."
        )
        return

    topic = update.message.text.strip()
    platform = state["platform"]

    await update.message.chat.send_action("typing")

    prompt_template = PLATFORM_PROMPTS[platform]
    prompt = prompt_template.format(topic=topic)

    try:
        response = model.generate_content(prompt)
        ideas_text = response.text
    except Exception as e:
        logger.exception("Gemini API error")
        await update.message.reply_text(
            "Something went wrong generating ideas. Try again in a moment."
        )
        return

    await update.message.reply_text(ideas_text)

    keyboard = [
        [InlineKeyboardButton(label, callback_data=key)]
        for key, label in PLATFORM_LABELS.items()
    ]
    await update.message.reply_text(
        "Want more? Send another topic, or pick a different platform:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(platform_chosen))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
