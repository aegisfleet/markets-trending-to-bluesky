MODEL_NAME = 'gemma-4-31b-it'
FALLBACK_MODELS = ['gemma-4-26b-a4b-it', 'gemini-3.8-flash']

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

def _is_retryable_error(e: Exception) -> tuple[bool, bool, bool]:
    """エラー種別を判定し、(is_rate_limit, is_server_error, is_model_unavailable) を返す"""
    msg = str(e)
    code = getattr(e, "code", None)
    is_rate_limit = (code in (429, 8)) or ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg)
    is_server_error = (code in (500, 503, 13, 14)) or any(
        k in msg for k in ("500", "INTERNAL", "503", "UNAVAILABLE")
    )
    is_model_unavailable = (code in (404, 5)) or any(
        k in msg for k in ("404", "NOT_FOUND", "no longer available")
    )
    return is_rate_limit, is_server_error, is_model_unavailable

def _is_fatal_error(e: Exception) -> bool:
    """認証エラーなど、リトライもモデル切り替えも無効な致命的エラーかどうかを判定する"""
    is_rate_limit, is_server_error, is_model_unavailable = _is_retryable_error(e)
    return not (is_rate_limit or is_server_error or is_model_unavailable)

def _handle_attempt_error(
    e: Exception,
    attempt: int,
    max_retries: int,
    model: str,
    initial_delay: float,
    backoff_factor: float,
) -> None:
    """試行失敗時のエラーを検証し、同一モデル内で再試行可能なら待機し、不可なら例外を送出する"""
    is_rate_limit, is_server_error, _ = _is_retryable_error(e)
    is_retryable_now = (is_rate_limit or is_server_error) and (attempt < max_retries - 1)
    if not is_retryable_now:
        raise e

    delay = initial_delay * (backoff_factor ** attempt)
    print(
        f"Gemini API 一時エラー ({e})。{delay:.1f} 秒後に再試行する "
        f"(モデル: {model}, 試行 {attempt + 1}/{max_retries})..."
    )
    time.sleep(delay)

def _generate_with_single_model(
    client: genai.Client,
    model: str,
    prompt_text: str,
    config: types.GenerateContentConfig,
    max_retries: int,
    initial_delay: float,
    backoff_factor: float,
) -> str:
    """単一モデルに対してテキスト生成を試み、一時エラー時は指数バックオフで再試行する"""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=config,
            )
            return extract_answer_text(response)
        except Exception as e:
            _handle_attempt_error(e, attempt, max_retries, model, initial_delay, backoff_factor)
    raise RuntimeError(f"モデル '{model}' の試行が完了しなかった。")

def _log_fallback(e: Exception, current_model: str, next_model: str, max_retries: int) -> None:
    """フォールバックモデル切り替え時のログを出力する"""
    _, _, is_model_unavailable = _is_retryable_error(e)
    if is_model_unavailable:
        print(f"Gemini API モデル利用不可エラー ({e})。フォールバックモデル '{next_model}' に直ちに切り替えて再試行する...")
    else:
        print(
            f"モデル '{current_model}' で {max_retries} 回の試行が失敗した。"
            f"フォールバックモデル '{next_model}' に切り替えて再試行する..."
        )

def generate_text_with_gemini(
    api_key: str,
    prompt_text: str,
    max_retries_per_model: int = 5,
    max_retries: int | None = None,
) -> str:
    """
    Gemini API を使用してテキストを生成する。
    各モデルに対して最大5回（設定値）の一時的エラー（レートリミット/サーバーエラー）のリトライを行い、
    失敗した場合はフォールバックモデルに順次切り替える（全モデルで合計15回）。

    Args:
        api_key: The Gemini API key.
        prompt_text: The prompt to send to the model.
        max_retries_per_model: 各モデルごとの最大試行回数 (デフォルト: 5).
        max_retries: 後方互換用パラメータ（指定された場合は max_retries_per_model として扱う）。

    Returns:
        生成されたテキスト。

    Raises:
        Exception: 全モデルの全リトライが失敗した場合、またはリトライ不可能なエラーが発生した場合。
    """
    if max_retries is not None:
        max_retries_per_model = max_retries

    initial_delay = 2.0
    backoff_factor = 2.0

    client = genai.Client(api_key=api_key)
    config = get_generation_config()

    models_to_try = [MODEL_NAME] + [m for m in FALLBACK_MODELS if m != MODEL_NAME]
    last_exception = None

    for model_idx, current_model in enumerate(models_to_try):
        has_next_model = (model_idx + 1) < len(models_to_try)
        next_model = models_to_try[model_idx + 1] if has_next_model else None

        try:
            return _generate_with_single_model(
                client=client,
                model=current_model,
                prompt_text=prompt_text,
                config=config,
                max_retries=max_retries_per_model,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
            )
        except Exception as e:
            last_exception = e
            if _is_fatal_error(e) or not has_next_model:
                break
            _log_fallback(e, current_model, next_model, max_retries_per_model)
            time.sleep(initial_delay)

    if last_exception:
        if not _is_fatal_error(last_exception):
            print(
                f"すべてのモデル ({len(models_to_try)} 個、各 {max_retries_per_model} 回、計 {len(models_to_try) * max_retries_per_model} 回) で試行が失敗した。"
            )
        raise last_exception

    raise RuntimeError("利用可能なモデルが存在しない。")
