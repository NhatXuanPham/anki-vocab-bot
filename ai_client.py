"""
Gọi Groq API để giải nghĩa 1 từ vựng, trả về dict có cấu trúc
sẵn sàng để nhét vào thẻ Anki.
"""
import json
import os
import re

from dotenv import load_dotenv
import requests

load_dotenv()

_IRREGULAR_LEMMAS = {
    "went": "go",
    "gone": "go",
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    "children": "child",
    "men": "man",
    "women": "woman",
    "teeth": "tooth",
    "feet": "foot",
    "mice": "mouse",
    "geese": "goose",
}


def _lemmatize(word: str) -> str:
    raw = word.strip()
    if not raw or " " in raw or "-" in raw:
        return raw

    lower = raw.lower()
    if lower in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[lower]

    if lower.endswith("ies") and len(lower) > 4:
        return lower[:-3] + "y"

    if lower.endswith("ing") and len(lower) > 5:
        stem = lower[:-3]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            return stem[:-1]
        return stem

    if lower.endswith("ed") and len(lower) > 4:
        stem = lower[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            return stem[:-1]
        return stem

    if lower.endswith("s") and len(lower) > 3 and not lower.endswith(("ss", "us", "is")):
        return lower[:-1]

    return raw


GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("GEMINI_MODEL", "llama-3.3-70b-versatile"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_TEMPLATE = """Bạn là trợ lý từ điển. Hãy giải nghĩa từ vựng tiếng Anh sau
và trả về DUY NHẤT một JSON object hợp lệ, không thêm text nào khác,
không dùng markdown code fence. Cấu trúc JSON bắt buộc:

{{
    "word": "từ người dùng đã nhập, giữ nguyên dạng gốc",
    "base_word": "dạng nguyên mẫu hoặc từ điển; nếu đã là dạng gốc thì giống word",
  "phonetic": "phiên âm IPA, ví dụ /wɜːd/",
  "part_of_speech": "từ loại viết tắt, ví dụ n., v., adj., adv.",
  "meaning_vi": "nghĩa tiếng Việt ngắn gọn, dễ hiểu",
  "meaning_en": "định nghĩa tiếng Anh ngắn gọn",
  "example_en": "1 câu ví dụ tiếng Anh dùng từ này",
  "example_vi": "bản dịch tiếng Việt của câu ví dụ trên"
}}

Nếu từ có nhiều nghĩa, chỉ lấy nghĩa phổ biến/thường dùng nhất.
Nếu input không phải một từ/cụm từ tiếng Anh hợp lệ, vẫn cố gắng suy đoán
nghĩa hợp lý nhất có thể.

Lưu ý:
- Giải thích theo từ người dùng nhập, không tự thay word bằng base_word.
- Nếu là dạng biến đổi của một từ khác, hãy điền base_word.
- Nếu đã là từ điển gốc, base_word phải bằng word.

Từ vựng cần giải nghĩa: "{word}"
Base form gợi ý: "{lemma_word}"
"""


class AIExplainError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _extract_response_text(response_json: dict) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise AIExplainError(f"Groq trả về cấu trúc không hợp lệ: {response_json!r}") from e

    if isinstance(content, str):
        if not content.strip():
            raise AIExplainError(f"Groq không trả về text: {response_json!r}")
        return content

    if isinstance(content, list):
        texts = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else None
            if text:
                texts.append(text)
        if texts:
            return "".join(texts)

    raise AIExplainError(f"Groq không trả về text: {response_json!r}")


def explain_word(word: str) -> dict:
    """Gọi Groq để lấy nghĩa của `word`, trả về dict theo schema ở trên."""
    global GROQ_API_KEY, GROQ_MODEL
    if not GROQ_API_KEY:
        load_dotenv()
        GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("GEMINI_MODEL", "llama-3.3-70b-versatile"))

    if not GROQ_API_KEY:
        raise AIExplainError("Thiếu GROQ_API_KEY trong file .env")

    original_word = word.strip()
    lemma_word = _lemmatize(original_word)
    prompt = PROMPT_TEMPLATE.format(word=original_word, lemma_word=lemma_word)
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            },
            timeout=30,
        )
        response.raise_for_status()
        raw_text = _extract_response_text(response.json())
    except Exception as e:
        raise AIExplainError(f"Lỗi gọi Groq API: {e}") from e

    try:
        data = _extract_json(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        raise AIExplainError(
            f"Groq trả về không đúng định dạng JSON: {raw_text!r}"
        ) from e

    required_fields = [
        "word", "base_word", "phonetic", "part_of_speech",
        "meaning_vi", "meaning_en", "example_en", "example_vi",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise AIExplainError(f"Thiếu field trong JSON trả về: {missing}")

    if not data.get("base_word"):
        data["base_word"] = data["word"]

    return data
