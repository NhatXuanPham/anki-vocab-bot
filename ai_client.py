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

# Provider configuration
PROVIDERS = {
    "groq": {
        "api_key": os.getenv("GROQ_API_KEY"),
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "api_url": "https://api.groq.com/openai/v1/chat/completions",
    },
    "gemini": {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest"),
        # Chrome uses API key in query param and expects model in URL
        "api_url_template": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
    },
    "cohere": {
        "api_key": os.getenv("COHERE_API_KEY"),
        "model": os.getenv("COHERE_MODEL", "command-r-plus"),
        "api_url": "https://api.cohere.com/v1/chat",
    },
    "litellm": {
        "api_key": os.getenv("LITELLM_API_KEY") or None,  # optional master key
        "model": os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
        "api_url": os.getenv(
            "LITELLM_API_URL",
            "http://localhost:4000/v1/chat/completions",
        ),
    },
}
# Get AI provider from environment
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

# Validate provider
AVAILABLE_PROVIDERS = list(PROVIDERS.keys())
if AI_PROVIDER not in AVAILABLE_PROVIDERS:
    raise ValueError(
        f"Invalid AI_PROVIDER: {AI_PROVIDER}. "
        f"Available providers: {', '.join(AVAILABLE_PROVIDERS)}"
    )

# Get current provider config
CURRENT_PROVIDER = PROVIDERS[AI_PROVIDER]

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


def _normalize_litellm_url(url: str) -> str:
    """Accept base, /v1, or full chat path; always return chat completions URL."""
    normalized = (url or "").strip().rstrip("/")
    if not normalized:
        return "http://localhost:4000/v1/chat/completions"
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _reload_provider_config(provider_name: str) -> dict:
    """Rebuild provider settings from current env (useful after .env edits)."""
    if provider_name == "litellm":
        return {
            "api_key": os.getenv("LITELLM_API_KEY") or None,
            "model": os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
            "api_url": _normalize_litellm_url(
                os.getenv(
                    "LITELLM_API_URL",
                    "http://localhost:4000/v1/chat/completions",
                )
            ),
        }

    config = dict(PROVIDERS[provider_name])
    if provider_name == "groq":
        config["api_key"] = os.getenv("GROQ_API_KEY")
        config["model"] = os.getenv("GROQ_MODEL", config["model"])
    elif provider_name == "gemini":
        config["api_key"] = os.getenv("GEMINI_API_KEY")
        config["model"] = os.getenv("GEMINI_MODEL", config["model"])
    elif provider_name == "cohere":
        config["api_key"] = os.getenv("COHERE_API_KEY")
        config["model"] = os.getenv("COHERE_MODEL", config["model"])
    return config


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


def _extract_response_text(response_json: dict, provider: str) -> str:
    """Extract text response from different provider formats."""
    try:
        if provider == "groq":
            content = response_json["choices"][0]["message"]["content"]
        elif provider == "gemini":
            # Gemini response format: candidates -> output
            candidates = response_json.get("candidates", [])
            if candidates:
                # Each candidate has 'output' field containing the generated text
                content = candidates[0].get("output", "")
            else:
                content = ""
        elif provider == "cohere":
            # Cohere response format: 'text' field in the top-level response
            content = response_json.get("text", "")
        elif provider == "litellm":
            # LiteLLM uses OpenAI-compatible format
            content = response_json["choices"][0]["message"]["content"]
        else:
            content = response_json.get("content", "")
            
        if isinstance(content, str):
            if not content.strip():
                raise AIExplainError(f"{provider.capitalize()} không trả về text: {response_json!r}")
            return content

        if isinstance(content, list):
            texts = []
            for part in content:
                text = part.get("text") if isinstance(part, dict) else None
                if text:
                    texts.append(text)
            if texts:
                return "".join(texts)

        raise AIExplainError(f"{provider.capitalize()} không trả về text: {response_json!r}")
    except (KeyError, IndexError, TypeError) as e:
        raise AIExplainError(f"{provider.capitalize()} trả về cấu trúc không hợp lệ: {response_json!r}") from e


def explain_word(word: str) -> dict:
    """Gọi AI provider để lấy nghĩa của `word`, trả về dict theo schema ở trên."""
    global AI_PROVIDER, CURRENT_PROVIDER
    
    # Reload environment variables in case they changed
    load_dotenv(override=True)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()
    
    # Re-validate provider
    AVAILABLE_PROVIDERS = list(PROVIDERS.keys())
    if AI_PROVIDER not in AVAILABLE_PROVIDERS:
        raise AIExplainError(
            f"Invalid AI_PROVIDER: {AI_PROVIDER}. "
            f"Available providers: {', '.join(AVAILABLE_PROVIDERS)}"
        )
    
    # Get current provider config
    CURRENT_PROVIDER = _reload_provider_config(AI_PROVIDER)
    PROVIDERS[AI_PROVIDER] = CURRENT_PROVIDER
    provider_name = AI_PROVIDER
    api_key = CURRENT_PROVIDER["api_key"]
    model = CURRENT_PROVIDER["model"]
    api_url = CURRENT_PROVIDER.get("api_url") or CURRENT_PROVIDER.get("api_url_template")
    
    if not api_key:
        if provider_name == "litellm":
            raise AIExplainError(
                "Missing LITELLM_API_KEY. LiteLLM proxy requires a virtual key "
                "(thường bắt đầu bằng 'sk-')."
            )
        raise AIExplainError(f"Missing API key for provider: {provider_name}")

    original_word = word.strip()
    lemma_word = _lemmatize(original_word)
    prompt = PROMPT_TEMPLATE.format(word=original_word, lemma_word=lemma_word)
    
    try:
        # Prepare headers and payload based on provider
        if provider_name == "gemini":
            headers = {
                "Content-Type": "application/json",
            }
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2000,
                }
            }
            # Add API key to URL for Gemini
            if api_key:
                api_url_with_key = api_url.format(model=model, api_key=api_key)
            else:
                api_url_with_key = api_url
        else:
            # OpenAI-compatible format (Groq, Cohere, LiteLLM)
            headers = {
                "Content-Type": "application/json",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            }
            api_url_with_key = api_url
        
        response = requests.post(
            api_url_with_key,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        raw_text = _extract_response_text(response.json(), provider_name)
    except Exception as e:
        raise AIExplainError(f"Lỗi gọi {provider_name.capitalize()} API: {e}") from e

    try:
        data = _extract_json(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        raise AIExplainError(
            f"{provider_name.capitalize()} trả về không đúng định dạng JSON: {raw_text!r}"
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
