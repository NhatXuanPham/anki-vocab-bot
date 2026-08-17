import json
import os
import re

from dotenv import load_dotenv
import requests

load_dotenv()

# OpenAI-compatible LLM configuration
AI_API_URL = os.getenv("AI_API_URL", "http://localhost:4000/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "gemini/gemini-3.5-flash")
AI_API_KEY = os.getenv("AI_API_KEY", "sk-1234")

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


PROMPT_TEMPLATE ="""You are a dictionary assistant. Define the following English vocabulary word
and return ONLY a valid JSON object, without any additional text,
and without using markdown code fences. The required JSON structure is:

{{
"word": "the word entered by the user, preserving its exact input form",
"base_word": "lemma or dictionary form; if already a base form, identical to word",
"phonetic": "IPA phonetic transcription, e.g., /wɜːd/",
"part_of_speech": "abbreviated part of speech, e.g., n., v., adj., adv.",
"meaning_vi": "concise and easy-to-understand Vietnamese definition",
"meaning_en": "concise English definition",
"example_en": "1 English example sentence using this word",
"example_vi": "Vietnamese translation of the example sentence above"
}}

If the word has multiple meanings, pick only the most common/frequently used one.
If the input is not a valid English word/phrase, still try your best to infer
the most reasonable meaning possible.

Notes:

Explain according to the word entered by the user; do not replace word with base_word.

If it is an inflected form of another word, fill in base_word.

If it is already a dictionary base form, base_word must equal word.

Vocabulary word to define: "{word}"
Suggested base form: "{lemma_word}"
"""


class AIExplainError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def explain_word(word: str) -> dict:
    # Reload environment variables in case they changed
    load_dotenv(override=True)
    api_url = os.getenv("AI_API_URL", "http://localhost:4000/v1/chat/completions")
    model = os.getenv("AI_MODEL", "gemini/gemini-3.5-flash")
    api_key = os.getenv("AI_API_KEY", "sk-1234")

    if not api_key:
        raise AIExplainError("Missing AI_API_KEY in environment variables")

    original_word = word.strip()
    lemma_word = _lemmatize(original_word)
    prompt = PROMPT_TEMPLATE.format(word=original_word, lemma_word=lemma_word)

    try:
        # OpenAI-compatible format
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        response_json = response.json()

        # Extract content from OpenAI-compatible response
        try:
            content = response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIExplainError(f"Invalid API response format: {response_json!r}") from e
    
        if not isinstance(content, str) or not content.strip():
            raise AIExplainError(f"API returned empty content: {response_json!r}")

        raw_text = content

    except requests.exceptions.RequestException as e:
        raise AIExplainError(f"Error calling LLM API: {e}") from e
    except Exception as e:
        raise AIExplainError(f"Error calling LLM API: {e}") from e

    try:
        data = _extract_json(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        raise AIExplainError(
            f"API response is not in valid JSON format: {raw_text!r}"
        ) from e

    required_fields = [
        "word", "base_word", "phonetic", "part_of_speech",
        "meaning_vi", "meaning_en", "example_en", "example_vi",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise AIExplainError(f"Missing fields in returned JSON: {missing}")

    if not data.get("base_word"):
        data["base_word"] = data["word"]

    return data
