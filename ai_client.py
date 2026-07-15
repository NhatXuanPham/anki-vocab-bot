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

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("GEMINI_MODEL", "llama-3.3-70b-versatile"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_TEMPLATE = """Bạn là trợ lý từ điển. Hãy giải nghĩa từ vựng tiếng Anh sau
và trả về DUY NHẤT một JSON object hợp lệ, không thêm text nào khác,
không dùng markdown code fence. Cấu trúc JSON bắt buộc:

{{
  "word": "từ gốc, viết đúng chính tả chuẩn",
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

Từ vựng cần giải nghĩa: "{word}"
"""


class AIExplainError(Exception):
    pass


def _extract_json(text: str) -> dict:
    # Gemini đôi khi vẫn bọc trong ```json ... ``` dù đã dặn không làm vậy
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _extract_response_text(response_json: dict) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise GeminiExplainError(f"Groq trả về cấu trúc không hợp lệ: {response_json!r}") from e

    if isinstance(content, str):
        if not content.strip():
            raise GeminiExplainError(f"Groq không trả về text: {response_json!r}")
        return content

    if isinstance(content, list):
        texts = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else None
            if text:
                texts.append(text)
        if texts:
            return "".join(texts)

    raise GeminiExplainError(f"Groq không trả về text: {response_json!r}")


def explain_word(word: str) -> dict:
    """Gọi Groq để lấy nghĩa của `word`, trả về dict theo schema ở trên."""
    global GROQ_API_KEY, GROQ_MODEL
    if not GROQ_API_KEY:
        load_dotenv()
        GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("GEMINI_MODEL", "llama-3.3-70b-versatile"))

    if not GROQ_API_KEY:
        raise GeminiExplainError("Thiếu GROQ_API_KEY trong file .env")

    prompt = PROMPT_TEMPLATE.format(word=word)
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
        raise GeminiExplainError(f"Lỗi gọi Groq API: {e}") from e

    try:
        data = _extract_json(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        raise GeminiExplainError(
            f"Groq trả về không đúng định dạng JSON: {raw_text!r}"
        ) from e

    required_fields = [
        "word", "phonetic", "part_of_speech",
        "meaning_vi", "meaning_en", "example_en", "example_vi",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise GeminiExplainError(f"Thiếu field trong JSON trả về: {missing}")

    return data
