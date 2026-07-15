"""
Giao tiếp với Anki qua addon AnkiConnect (https://ankiweb.net/shared/info/2055492159).
Yêu cầu: Anki phải đang MỞ trên máy này, và đã cài addon AnkiConnect.
"""
import base64
import os
import re
from urllib.parse import quote, urljoin

import requests

ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL", "http://127.0.0.1:8765")
ANKI_DECK_NAME = os.getenv("ANKI_DECK_NAME", "Vocab AI")
ANKI_MODEL_NAME = os.getenv("ANKI_MODEL_NAME", "Vocab (AI)")
AUDIO_FIELD_NAME = "Audio"
CAMBRIDGE_BASE_URL = "https://dictionary.cambridge.org"
CAMBRIDGE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

FIELDS = [
    "Word", "Phonetic", "PartOfSpeech",
    "MeaningVi", "MeaningEn", "ExampleEn", "ExampleVi", AUDIO_FIELD_NAME,
]

FRONT_TEMPLATE = """
<div style="font-size:28px; text-align:center;">{{Word}}</div>
<div style="text-align:center; color:#666;">{{Phonetic}} &nbsp; <i>{{PartOfSpeech}}</i></div>
<div style="text-align:center; margin-top:8px;">{{Audio}}</div>
"""

BACK_TEMPLATE = """
{{FrontSide}}
<hr id="answer">
<div style="font-size:20px;"><b>{{MeaningVi}}</b></div>
<div style="color:#666; margin-top:4px;">{{MeaningEn}}</div>
<div style="margin-top:12px;">{{ExampleEn}}</div>
<div style="color:#666;">{{ExampleVi}}</div>
"""

CSS = """
.card {
  font-family: Arial, sans-serif;
  color: #1a1a1a;
  background-color: #fafafa;
  padding: 16px;
}
"""


class AnkiConnectError(Exception):
    pass


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _cambridge_word_url(word: str) -> str:
    return f"{CAMBRIDGE_BASE_URL}/vi/dictionary/english/{quote(word.strip())}"


def _extract_cambridge_mp3_url(page_html: str) -> str | None:
    patterns = [
        r'<span class="uk dpron-i.*?<source type="audio/mpeg" src="([^"]+\.mp3)"',
        r'<span class="us dpron-i.*?<source type="audio/mpeg" src="([^"]+\.mp3)"',
        r'<source type="audio/mpeg" src="([^"]+\.mp3)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return urljoin(CAMBRIDGE_BASE_URL, match.group(1))

    return None


def find_mp3_for_word(word: str) -> dict | None:
    """Lấy mp3 pronunciation từ trang Cambridge của từ cần tra."""
    page_url = _cambridge_word_url(word)
    try:
        response = requests.get(
            page_url,
            headers={"User-Agent": CAMBRIDGE_USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    audio_url = _extract_cambridge_mp3_url(response.text)
    if not audio_url:
        return None

    try:
        audio_response = requests.get(
            audio_url,
            headers={"User-Agent": CAMBRIDGE_USER_AGENT, "Referer": page_url},
            timeout=30,
        )
        audio_response.raise_for_status()
    except requests.RequestException:
        return None

    return {
        "filename": os.path.basename(audio_url),
        "data": base64.b64encode(audio_response.content).decode("ascii"),
    }


def _invoke(action: str, **params):
    payload = {"action": action, "version": 6, "params": params}
    try:
        resp = requests.post(ANKI_CONNECT_URL, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise AnkiConnectError(
            "Không kết nối được tới AnkiConnect. Kiểm tra: "
            "1) Anki đang mở, 2) đã cài addon AnkiConnect, "
            f"3) URL đúng ({ANKI_CONNECT_URL}). Lỗi gốc: {e}"
        ) from e

    result = resp.json()
    if result.get("error") is not None:
        raise AnkiConnectError(f"AnkiConnect trả lỗi: {result['error']}")
    return result["result"]


def ensure_deck_and_model_exist():
    """Tạo deck và note type nếu chưa tồn tại. Gọi 1 lần lúc bot khởi động."""
    decks = _invoke("deckNames")
    if ANKI_DECK_NAME not in decks:
        _invoke("createDeck", deck=ANKI_DECK_NAME)

    models = _invoke("modelNames")
    if ANKI_MODEL_NAME not in models:
        _invoke(
            "createModel",
            modelName=ANKI_MODEL_NAME,
            inOrderFields=FIELDS,
            css=CSS,
            cardTemplates=[
                {
                    "Name": "Card 1",
                    "Front": FRONT_TEMPLATE,
                    "Back": BACK_TEMPLATE,
                }
            ],
        )
        return

    field_names = _invoke("modelFieldNames", modelName=ANKI_MODEL_NAME)
    if AUDIO_FIELD_NAME not in field_names:
        _invoke(
            "modelFieldAdd",
            modelName=ANKI_MODEL_NAME,
            fieldName=AUDIO_FIELD_NAME,
            index=len(field_names),
        )

    templates = _invoke("modelTemplates", modelName=ANKI_MODEL_NAME)
    for template_name, template in templates.items():
        front = template.get("Front", "")
        if "{{Audio}}" not in front:
            updated_front = front.rstrip() + "\n<div style=\"text-align:center; margin-top:8px;\">{{Audio}}</div>"
            _invoke(
                "modelTemplateAdd",
                modelName=ANKI_MODEL_NAME,
                template={
                    "Name": template_name,
                    "Front": updated_front,
                    "Back": template.get("Back", ""),
                },
            )


def add_vocab_note(data: dict, tags=None, audio_media: dict | None = None) -> int:
    """
    Thêm 1 note vào Anki từ dict trả về bởi ai_client.explain_word().
    Trả về note ID nếu thành công.
    """
    note = {
        "deckName": ANKI_DECK_NAME,
        "modelName": ANKI_MODEL_NAME,
        "fields": {
            "Word": data["word"],
            "Phonetic": data["phonetic"],
            "PartOfSpeech": data["part_of_speech"],
            "MeaningVi": data["meaning_vi"],
            "MeaningEn": data["meaning_en"],
            "ExampleEn": data["example_en"],
            "ExampleVi": data["example_vi"],
            AUDIO_FIELD_NAME: "",
        },
        "options": {
            "allowDuplicate": False,
            "duplicateScope": "deck",
        },
        "tags": tags or ["ai-generated"],
    }
    if audio_media is not None:
        note["audio"] = {
            "filename": audio_media["filename"],
            "data": audio_media["data"],
            "fields": [AUDIO_FIELD_NAME],
        }
    note_id = _invoke("addNote", note=note)
    if note_id is None:
        raise AnkiConnectError(
            f"Thẻ '{data['word']}' có thể đã tồn tại trong deck (bị chặn trùng lặp)."
        )
    return note_id
