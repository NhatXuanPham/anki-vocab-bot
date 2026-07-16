"""
Telegram bot: nhận 1 từ vựng -> gọi AI giải nghĩa -> tạo thẻ trong Anki
(qua AnkiConnect, Anki phải đang mở trên máy chạy bot này).

Chạy: python bot.py
"""
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

from anki_client import AnkiConnectError, add_vocab_note, ensure_deck_and_model_exist, find_mp3_for_word
from ai_client import AIExplainError, explain_word

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
        "Gửi cho tôi 1 từ tiếng Anh, tôi sẽ giải nghĩa bằng AI, lấy MP3 từ "
        "Cambridge nếu có, rồi tự tạo thẻ Anki cho bạn (nhớ mở sẵn Anki trên máy nhé)."
    )


async def handle_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("Bạn không có quyền dùng bot này.")
        return

    word = update.message.text.strip()
    if not word:
        return

    status_msg = await update.message.reply_text(f"Đang tra '{word}'...")

    try:
        data = explain_word(word)
    except AIExplainError as e:
        await status_msg.edit_text(f"Lỗi khi giải nghĩa: {e}")
        return

    audio_media = find_mp3_for_word(word, data.get("base_word"))

    try:
        add_vocab_note(data, audio_media=audio_media)
    except AnkiConnectError as e:
        await status_msg.edit_text(f"Lấy nghĩa xong nhưng lỗi khi thêm vào Anki: {e}")
        return

    audio_line = (
        f"\n🔊 Đã đính kèm MP3 Cambridge: {audio_media['filename']}"
        if audio_media is not None
        else "\n🔇 Không tìm thấy MP3 Cambridge phù hợp"
    )
    base_word_line = ""
    base_word = (data.get("base_word") or "").strip()
    if base_word and base_word.casefold() != data["word"].strip().casefold():
        base_word_line = f"Base word: {base_word}\n"

    reply = (
        f"✅ Đã thêm thẻ: {data['word']} {data['phonetic']} ({data['part_of_speech']})\n"
        f"{base_word_line}"
        f"🇻🇳 {data['meaning_vi']}\n"
        f"🇬🇧 {data['meaning_en']}\n"
        f"📝 {data['example_en']}\n"
        f"   {data['example_vi']}"
        f"{audio_line}"
    )
    await status_msg.edit_text(reply)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Thiếu TELEGRAM_BOT_TOKEN trong file .env")

    try:
        ensure_deck_and_model_exist()
        logger.info("Đã kiểm tra/tạo deck và note type trong Anki.")
    except AnkiConnectError as e:
        raise SystemExit(
            f"Không kết nối được Anki lúc khởi động: {e}\n"
            "Hãy mở Anki (có cài addon AnkiConnect) rồi chạy lại bot."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word))

    logger.info("Bot đang chạy...")
    app.run_polling()


if __name__ == "__main__":
    main()