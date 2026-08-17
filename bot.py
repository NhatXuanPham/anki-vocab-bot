import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

from anki_client import (
    AnkiConnectError,
    add_vocab_note,
    ensure_deck_and_model_exist,
    find_mp3_for_word,
    get_existing_vocab_data,
)
from ai_client import AIExplainError, explain_word, lemmatize

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_allowed_ids_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
ALLOWED_USER_IDS = (
    {int(x) for x in _allowed_ids_raw.split(",") if x.strip()}
    if _allowed_ids_raw
    else None
)


def _is_allowed(user_id: int) -> bool:
    return ALLOWED_USER_IDS is None or user_id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me an English word, and I will explain its meaning using AI, retrieve audio "
        "from Cambridge if available, and automatically create an Anki card for you "
        "(make sure Anki is running on your machine)."
    )


def _build_reply(
    data: dict,
    audio_media: dict | None = None,
    title: str = "Card added",
) -> str:
    if audio_media is not None:
        audio_line = f"\n🔊 Cambridge MP3 attached: {audio_media['filename']}"
    elif data.get("audio"):
        audio_line = f"\n🔊 Audio: {data['audio']}"
    else:
        audio_line = "\n🔇 No suitable Cambridge MP3 found"

    base_word_line = ""
    base_word = (data.get("base_word") or "").strip()
    if base_word and base_word.casefold() != data["word"].strip().casefold():
        base_word_line = f"Base word: {base_word}\n"
    return (
        f"✅ {title}: {data['word']} {data['phonetic']} ({data['part_of_speech']})\n"
        f"{base_word_line}"
        f"🇻🇳 {data['meaning_vi']}\n"
        f"🇬🇧 {data['meaning_en']}\n"
        f"📝 {data['example_en']}\n"
        f"   {data['example_vi']}"
        f"{audio_line}"
    )


async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    word = update.message.text.strip()
    if not word:
        return

    status_msg = await update.message.reply_text(f"Looking up '{word}'...")

    try:
        lemma = lemmatize(word)
        existing_data = get_existing_vocab_data(word, base_word=lemma)
        if existing_data is not None:
            await status_msg.edit_text(
                _build_reply(
                    existing_data,
                    title="Already in Anki",
                )
            )
            return

        data = explain_word(word)
    except AIExplainError as e:
        await status_msg.edit_text(f"Error explaining word: {e}")
        return

    audio_media = find_mp3_for_word(word, data.get("base_word"))

    try:
        add_vocab_note(data, audio_media=audio_media)
    except AnkiConnectError as e:
        if "duplicate" in str(e).lower():
            existing_data = get_existing_vocab_data(word, base_word=data.get("base_word"))
            if existing_data is not None:
                await status_msg.edit_text(
                    _build_reply(
                        existing_data,
                        title="Already in Anki",
                    )
                )
                return
            await status_msg.edit_text(
                _build_reply(
                    data,
                    audio_media=audio_media,
                    title="Already in Anki",
                )
            )
            return
        await status_msg.edit_text(f"Meaning retrieved, but failed to add to Anki: {e}")
        return

    await status_msg.edit_text(_build_reply(data, audio_media=audio_media, title="Card added"))


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env file")

    try:
        ensure_deck_and_model_exist()
        logger.info("Checked/created deck and note type in Anki.")
    except AnkiConnectError as e:
        raise SystemExit(
            f"Could not connect to Anki on startup: {e}\n"
            "Please open Anki (with the AnkiConnect add-on installed) and restart the bot."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()