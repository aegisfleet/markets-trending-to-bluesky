MODEL_NAME = 'gemma-4-31b-it'
FALLBACK_MODELS = ['gemini-2.5-flash']

import time
from google import genai
from google.genai import types


def get_generation_config():
    """AFC警告を抑制するためのGenerationConfigを返す"""
    return types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        )
    )


def extract_answer_text(response):
    """レスポンスから thinking パートを除外し、最終回答テキストのみを返す"""
    parts = response.candidates[0].content.parts
    answer_texts = []
    for part in parts:
        if getattr(part, 'thought', False):
            continue
        if part.text:
            answer_texts.append(part.text)
    return "".join(answer_texts)


def generate_text_with_gemini(api_key: str, prompt_text: str) -> str:
    """
    Generates text using the Gemini API with exponential backoff retry for rate limits
    and fallback to secondary models if internal server errors occur.

    Args:
        api_key: The Gemini API key.
        prompt_text: The prompt to send to the model.

    Returns:
        The generated text.

    Raises:
        Exception: If an error occurred and all retries failed.
    """
    max_retries = 5
    initial_delay = 2.0
    backoff_factor = 2.0

    client = genai.Client(api_key=api_key)
    config = get_generation_config()

    models_to_try = [MODEL_NAME] + [m for m in FALLBACK_MODELS if m != MODEL_NAME]
    current_model_idx = 0

    for attempt in range(max_retries):
        current_model = models_to_try[current_model_idx]
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=prompt_text,
                config=config,
            )
            return extract_answer_text(response)
        except Exception as e:
            error_msg = str(e)
            is_rate_limit = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg
            is_server_error = (
                "500" in error_msg or "INTERNAL" in error_msg or
                "503" in error_msg or "UNAVAILABLE" in error_msg
            )

            # Check code attribute if it exists
            code = getattr(e, "code", None)
            if code == 429 or code == 8:
                is_rate_limit = True
            elif code in (500, 503, 13, 14):
                is_server_error = True

            # サーバーエラー（500/503等）でフォールバックモデルが残っている場合は切り替え
            if is_server_error and (current_model_idx + 1) < len(models_to_try):
                current_model_idx += 1
                next_model = models_to_try[current_model_idx]
                print(f"Gemini API サーバーエラー ({error_msg}) を検出。フォールバックモデル '{next_model}' に切り替えて再試行する...")
                time.sleep(initial_delay)
                continue

            if (is_rate_limit or is_server_error) and attempt < max_retries - 1:
                delay = initial_delay * (backoff_factor ** attempt)
                print(f"Gemini API 一時エラー ({error_msg})。{delay:.1f} 秒後に再試行する (試行 {attempt + 1}/{max_retries}, モデル: {current_model})...")
                time.sleep(delay)
            else:
                raise e

