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

PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "youtube": "YouTube",
}

TONE_LABELS = {
    "funny": "Funny / Casual",
    "serious": "Serious / Authoritative",
    "educational": "Educational / How-to",
}

LENGTH_LABELS = {
    "short": "Short (15-30 sec)",
    "medium": "Medium (30-60 sec)",
    "long": "Long (60-90 sec)",
}

FIXED_NICHES = [
    "Wealth & Money",
    "Health & Wellness",
    "Psychology",
    "Dark History",
    "Football",
    "Luxury Lifestyle",
    "Mystery & Unsolved Cases",
    "Technology & AI",
    "Cars & Supercars",
    "Interesting Facts",
]


def call_gemini(prompt: str) -> str:
    response = model.generate_content(prompt)
    return response.text.strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"platform:{key}")]
        for key, label in PLATFORM_LABELS.items()
    ]
    await update.message.reply_text(
        "Pick a platform to get started:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def send_niches(query, context, platform):
    user_state[query.from_user.id]["niches"] = FIXED_NICHES

    keyboard = [
        [InlineKeyboardButton(niche, callback_data=f"niche:{i}")]
        for i, niche in enumerate(FIXED_NICHES)
    ]
    await query.message.reply_text(
        "Pick a niche:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def send_topics(query, context, platform, niche):
    await query.message.chat.send_action("typing")
    prompt = (
        f"Generate 10 specific {PLATFORM_LABELS[platform]} content topic ideas "
        f"within the niche '{niche}'. Each should be a short, specific concept "
        "(under 12 words). Return ONLY a numbered list 1-10, no extra text."
    )
    topics_text = call_gemini(prompt)
    topics = parse_numbered_list(topics_text)

    user_state[query.from_user.id]["topics"] = topics

    keyboard = [
        [InlineKeyboardButton(topic[:40], callback_data=f"topic:{i}")]
        for i, topic in enumerate(topics)
    ]
    await query.message.reply_text(
        "Pick a topic:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_tone(query, context):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"tone:{key}")]
        for key, label in TONE_LABELS.items()
    ]
    await query.message.reply_text(
        "What tone do you want?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_length(query, context):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"length:{key}")]
        for key, label in LENGTH_LABELS.items()
    ]
    await query.message.reply_text(
        "How long should the script be?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def generate_full_package(query, context, state):
    await query.message.chat.send_action("typing")

    platform = PLATFORM_LABELS[state["platform"]]
    topic = state["topics"][state["topic_index"]]
    tone = TONE_LABELS[state["tone"]]
    length = LENGTH_LABELS[state["length"]]

    script_prompt = (
        f"Write a {platform} video script about: '{topic}'. "
        f"Tone: {tone}. Length target: {length}. "
        "This must NOT read like a generic ad or textbook script. Write it like "
        "a real person talking to camera, with natural speech texture: include "
        "bracketed reaction cues like [chuckles], [pause], [sighs], [laughs], "
        "false starts, and casual phrasing where it fits the tone. "
        "Format as a line-by-line script with speaker cues and stage directions "
        "in brackets. Do not add any preamble or explanation, just the script."
    )
    script = call_gemini(script_prompt)

    image_prompt_prompt = (
        f"Write one detailed AI image-generation prompt (for tools like Midjourney "
        f"or DALL-E) for a thumbnail or key visual for this {platform} video about "
        f"'{topic}'. Describe subject, style, lighting, composition. "
        "Return ONLY the prompt text, no extra commentary."
    )
    image_prompt = call_gemini(image_prompt_prompt)

    video_prompt_prompt = (
        f"Here is a video script:\n\n{script}\n\n"
        f"Write one detailed AI video-generation prompt (for tools like Runway, "
        f"Luma, or Sora) that brings this exact script to life as a video. "
        "The prompt must describe: the setting/scene, what the character looks "
        "like, the specific actions the character performs (matching the stage "
        "directions and reactions in the script above), and the exact dialogue "
        "lines the character should be saying at each moment, in sync with those "
        "actions. Keep the dialogue verbatim from the script. Describe camera "
        "movement, pacing, and mood throughout. "
        "Return ONLY the prompt text, no extra commentary."
    )
    video_prompt = call_gemini(video_prompt_prompt)

    await query.message.reply_text(f"SCRIPT:\n\n{script}")
    await query.message.reply_text(f"IMAGE PROMPT:\n\n{image_prompt}")
    await query.message.reply_text(f"VIDEO PROMPT:\n\n{video_prompt}")

    await query.message.reply_text("Use /start to make another one.")


def parse_numbered_list(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    items = []
    for line in lines:
        cleaned = line
        for sep in [". ", ") ", " - "]:
            if sep in cleaned[:5]:
                cleaned = cleaned.split(sep, 1)[1]
                break
        cleaned = cleaned.strip("*# ")
        if cleaned:
            items.append(cleaned)
    return items[:10] if len(items) >= 10 else items


async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_state:
        user_state[user_id] = {}
    state = user_state[user_id]

    action, _, value = data.partition(":")

    if action == "platform":
        state["platform"] = value
        await query.edit_message_text(f"Platform: {PLATFORM_LABELS[value]}")
        await send_niches(query, context, value)

    elif action == "niche":
        index = int(value)
        niche = state["niches"][index]
        state["niche"] = niche
        await query.edit_message_text(f"Niche: {niche}")
        await send_topics(query, context, state["platform"], niche)

    elif action == "topic":
        index = int(value)
        state["topic_index"] = index
        await query.edit_message_text(f"Topic: {state['topics'][index]}")
        await ask_tone(query, context)

    elif action == "tone":
        state["tone"] = value
        await query.edit_message_text(f"Tone: {TONE_LABELS[value]}")
        await ask_length(query, context)

    elif action == "length":
        state["length"] = value
        await query.edit_message_text(f"Length: {LENGTH_LABELS[value]}")
        await generate_full_package(query, context, state)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_router))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
