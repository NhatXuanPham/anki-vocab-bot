"""
Giao tiếp với Anki qua addon AnkiConnect (https://ankiweb.net/shared/info/2055492159).
Yêu cầu: Anki phải đang MỞ trên máy này, và đã cài addon AnkiConnect.
"""
import os

import requests

ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL", "http://127.0.0.1:8765")
ANKI_DECK_NAME = os.getenv("ANKI_DECK_NAME", "Vocab AI")
ANKI_MODEL_NAME = os.getenv("ANKI_MODEL_NAME", "Vocab (AI)")

FIELDS = [
    "Word", "Phonetic", "PartOfSpeech",
    "MeaningVi", "MeaningEn", "ExampleEn", "ExampleVi",
]

FRONT_TEMPLATE = """
<div style="font-size:28px; text-align:center;">{{Word}}</div>
<div style="text-align:center; color:#666;">{{Phonetic}} &nbsp; <i>{{PartOfSpeech}}</i></div>
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


def add_vocab_note(data: dict, tags=None) -> int:
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
        },
        "options": {
            "allowDuplicate": False,
            "duplicateScope": "deck",
        },
        "tags": tags or ["ai-generated"],
    }
    note_id = _invoke("addNote", note=note)
    if note_id is None:
        raise AnkiConnectError(
            f"Thẻ '{data['word']}' có thể đã tồn tại trong deck (bị chặn trùng lặp)."
        )
    return note_id
