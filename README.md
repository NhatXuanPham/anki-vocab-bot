# Anki Vocab Bot (Telegram + OpenAI-compatible LLM + AnkiConnect)

Telegram Bot: Send an English word → the bot calls an OpenAI-compatible LLM API to get definitions, retrieves MP3 audio from Cambridge Dictionary if available, and automatically creates a card in Anki (via the AnkiConnect add-on; Anki must be running on the same machine as the bot).

## 1. Prerequisites

### a) Install AnkiConnect in Anki

1. Open Anki → **Tools → Add-ons → Get Add-ons...**
2. Enter code: `2055492159`
3. Restart Anki. AnkiConnect will now run a local server at `[http://127.0.0.1:8765](http://127.0.0.1:8765)` whenever Anki is open.

### b) Get a Telegram Bot Token

* Chat with [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → follow instructions → copy the token (e.g., `123456:ABC-DEF...`).

### c) Prepare the API (OpenAI-compatible)

You can use any provider:

* **LiteLLM Proxy** (localhost): Run a LiteLLM proxy locally.
* **OpenAI API**: Configure the official OpenAI endpoint.
* **Ollama**: Run a local LLM model.
* **Groq API**: Use the Groq endpoint.

## 2. Installation

```bash
cd anki_bot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp env.example .env
# Open .env and fill in TELEGRAM_BOT_TOKEN, AI_API_URL, AI_MODEL, AI_API_KEY

```

## 3. Usage

1. **Open Anki first** (to ensure the AnkiConnect server is running).
2. **Start the LLM API server** (if using a local setup):
3. Run the bot:
```bash
python bot.py

```


4. Open a chat with your newly created bot on Telegram → send `/start` → test with a word, e.g., `serendipity`.

The bot will automatically create a deck (`Vocab AI` by default) and a note type (`Vocab (AI)`) in Anki if they do not exist yet, using the following fields: `Word`, `Phonetic`, `PartOfSpeech`, `MeaningVi`, `MeaningEn`, `ExampleEn`, `ExampleVi`, `Audio`. The `Word` field automatically includes the base word when applicable, so a separate field for `BaseWord` is not required.

## 4. Customization

* **Change deck/note type name**: Modify `ANKI_DECK_NAME` and `ANKI_MODEL_NAME` in `.env`.
* **Change Groq model**: Modify `GROQ_MODEL` in `.env` (e.g., `llama-3.3-70b-versatile`).
* **Minimalist schema**: The bot saves the exact user input in the `Word` field, merging the base word directly into it if available. Other fields remain as configured: `Phonetic`, `PartOfSpeech`, `MeaningVi`, `MeaningEn`, `ExampleEn`, `ExampleVi`, `Audio`.
* **Cambridge Audio**: The bot opens `[https://dictionary.cambridge.org/vi/dictionary/english/](https://dictionary.cambridge.org/vi/dictionary/english/)<word>` to fetch the `.mp3` pronunciation file and attaches it to the `Audio` field in Anki. For inflected word forms, it prioritizes searching audio via the `BaseWord` while preserving the user's original `Word` entry.
* **Restrict access**: Add Telegram User IDs (not usernames) to `ALLOWED_TELEGRAM_USER_IDS` in `.env`, separated by commas. Obtain your user ID by chatting with [@userinfobot](https://t.me/userinfobot).
* **Customize card layout / Add fields** (e.g., adding images or extra audio): Modify `FIELDS`, `FRONT_TEMPLATE`, and `BACK_TEMPLATE` in `anki_client.py`. Note that updating code will not automatically modify existing note types in Anki; you must delete the existing note type in Anki for the bot to recreate it, or edit it manually in Anki.

## 5. Running in the Background (Optional)

To keep the bot running continuously, use `pm2`, `systemd` (Linux), or Task Scheduler (Windows) to autostart `python bot.py`. Since the bot requires Anki to be open, this approach is recommended if Anki remains running on your system.

## Project Structure

```
anki_bot/
├── bot.py             # Entrypoint, handles Telegram interaction
├── ai_client.py       # Calls AI API, parses word definitions (JSON)
├── anki_client.py     # Calls AnkiConnect, creates deck/note type/cards
├── requirements.txt
├── .env.example
└── README.md

```