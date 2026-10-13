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
    """APIエラー時のモデルフォールバックまたは待機処理を行い、(new_model_idx, should_switch) を返す"""
    _, _, should_switch = gemini_model._is_retryable_error(e)
    if should_switch and (current_model_idx + 1) < total_models:
        time.sleep(2)
        return current_model_idx + 1, True

    if retry_count < max_retries:
        wait_time = min(5 * (2 ** retry_count), 30)
        print(f"{wait_time}秒待機中...")
        time.sleep(wait_time)
    return current_model_idx, False

def get_description(api_key, text, limit_size, max_retries=5):
    client = genai.Client(api_key=api_key)
    config = gemini_model.get_generation_config()
    models = _get_model_candidates()

    current_model_idx = 0
    last_response_text = ""

    for retry_count in range(max_retries + 1):
        target_limit = limit_size - (retry_count * 20)
        prompt = text.replace("[limit_size]", str(target_limit))
        current_model = models[current_model_idx]

        try:
            return _request_content(client, current_model, prompt, limit_size, config)
        except ValueError as e:
            last_response_text = str(e)
            print(f"文字数超過/空レスポンスによるリトライ {retry_count}/{max_retries} (モデル: {current_model}): {e}")
            if retry_count < max_retries:
                time.sleep(3)
        except Exception as e:
            print(f"APIエラー {retry_count}/{max_retries} (モデル: {current_model}): {e}")
            current_model_idx, should_switch = _handle_api_error(
                e, retry_count, max_retries, current_model_idx, len(models)
            )
            if should_switch:
                print(f"モデルをフォールバックモデル '{models[current_model_idx]}' に切り替えて再試行する...")
                continue

    print("最大リトライ回数に達した。")
    if not last_response_text:
        return None
    return remove_last_sentence(last_response_text)
