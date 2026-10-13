from google import genai
import time
import gemini_model

def remove_last_sentence(text):
    sentences = text.split('。')
    if sentences[-1] == '':
        sentences.pop()
    if sentences:
        sentences.pop()
    if sentences:
        result = '。'.join(sentences) + '。'
        return result
    return ""

def _get_model_candidates():
    """試行するモデル候補のリストを返す"""
    models = [gemini_model.MODEL_NAME]
    for m in getattr(gemini_model, "FALLBACK_MODELS", ["gemini-3.8-flash"]):
        if m not in models:
            models.append(m)
    return models

def _request_content(client, model, prompt, limit_size, config):
    """Gemini API にコンテンツ生成を要求し、文字数と空文字の検証を行う"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    text = gemini_model.extract_answer_text(response)
    if not text or not text.strip():
        raise ValueError("レスポンスが空である。")
    if len(text) > limit_size:
        raise ValueError(
            f"レスポンスの文字数が{limit_size}文字を超えている。(実測: {len(text)}文字)"
        )
    return text

def _handle_api_error(e, retry_count, max_retries, current_model_idx, total_models):
    """APIエラー時のモデルフォールバックまたは待機処理を行い、(new_model_idx, should_switch) を返す（後方互換用）"""
    _, _, is_model_unavailable = gemini_model._is_retryable_error(e)
    if is_model_unavailable and (current_model_idx + 1) < total_models:
        time.sleep(2)
        return current_model_idx + 1, True

    if retry_count < max_retries:
        wait_time = min(5 * (2 ** retry_count), 30)
        print(f"{wait_time}秒待機中...")
        time.sleep(wait_time)
    return current_model_idx, False

def _handle_limit_error(
    e: ValueError,
    attempt: int,
    max_retries: int,
    current_model: str,
    next_model: str | None,
) -> bool:
    """文字数制限エラーを処理し、モデル切り替えが必要な場合は True を返す"""
    print(
        f"文字数超過/空レスポンスによるリトライ "
        f"(モデル: {current_model}, 試行 {attempt + 1}/{max_retries}): {e}"
    )
    if attempt < max_retries - 1:
        time.sleep(3)
        return False
    if next_model:
        print(
            f"モデル '{current_model}' で文字数制約を満たせなかったため、"
            f"フォールバックモデル '{next_model}' に切り替える..."
        )
        time.sleep(2)
        return True
    return False

def _handle_description_api_error(
    e: Exception,
    attempt: int,
    max_retries: int,
    current_model: str,
    next_model: str | None,
) -> bool:
    """APIエラーを処理し、モデル切り替えが必要な場合は True を返す"""
    print(
        f"APIエラー (モデル: {current_model}, 試行 {attempt + 1}/{max_retries}): {e}"
    )
    is_rate_limit, is_server_error, is_model_unavailable = gemini_model._is_retryable_error(e)

    if is_model_unavailable:
        if next_model:
            print(
                f"モデル '{current_model}' が利用不可のため、"
                f"フォールバックモデル '{next_model}' に直ちに切り替えて再試行する..."
            )
            time.sleep(2)
            return True
        print("すべてのモデルで利用不可エラーが発生した。")
        return False

    if not (is_rate_limit or is_server_error):
        print(f"致命的なエラーのためリトライを中断する: {e}")
        raise e

    if attempt < max_retries - 1:
        wait_time = min(5 * (2 ** attempt), 30)
        print(
            f"{wait_time}秒待機して再試行する "
            f"(モデル: {current_model}, 試行 {attempt + 1}/{max_retries})..."
        )
        time.sleep(wait_time)
        return False

    if next_model:
        print(
            f"モデル '{current_model}' で {max_retries} 回の試行が失敗した。"
            f"フォールバックモデル '{next_model}' に切り替える..."
        )
        time.sleep(2)
        return True
    return False

def _generate_description_for_model(
    client,
    current_model: str,
    next_model: str | None,
    text: str,
    limit_size: int,
    config,
    max_retries: int,
) -> tuple[str | None, str]:
    """単一モデルに対して要約生成を試みる。(result_text, last_error_text) を返す"""
    last_response_text = ""
    for attempt in range(max_retries):
        target_limit = limit_size - (attempt * 20)
        prompt = text.replace("[limit_size]", str(target_limit))

        try:
            return _request_content(client, current_model, prompt, limit_size, config), ""
        except ValueError as e:
            last_response_text = str(e)
            if _handle_limit_error(e, attempt, max_retries, current_model, next_model):
                break
        except Exception as e:
            if _handle_description_api_error(e, attempt, max_retries, current_model, next_model):
                break
    return None, last_response_text

def get_description(
    api_key: str,
    text: str,
    limit_size: int,
    max_retries: int = 5,
    max_retries_per_model: int | None = None,
):
    """Gemini API を用いて文字数制限を満たす説明文を生成する。
    各モデルに対して最大5回（設定値）の試行（文字数超過または一時的APIエラーのリトライ）を行い、
    失敗した場合はフォールバックモデルに順次切り替える（全モデルで合計15回）。
    """
    if max_retries_per_model is None:
        max_retries_per_model = max_retries

    client = genai.Client(api_key=api_key)
    config = gemini_model.get_generation_config()
    models = _get_model_candidates()
    last_response_text = ""

    for model_idx, current_model in enumerate(models):
        has_next_model = (model_idx + 1) < len(models)
        next_model = models[model_idx + 1] if has_next_model else None

        result, err_text = _generate_description_for_model(
            client, current_model, next_model, text, limit_size, config, max_retries_per_model
        )
        if result is not None:
            return result
        if err_text:
            last_response_text = err_text

    print(
        f"すべてのモデル ({len(models)} 個、各 {max_retries_per_model} 回、計 {len(models) * max_retries_per_model} 回) で最大試行回数に達した。"
    )
    if not last_response_text:
        return None
    return remove_last_sentence(last_response_text)
