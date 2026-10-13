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

def get_description(api_key, text, limit_size, max_retries=5):
    client = genai.Client(api_key=api_key)
    config = gemini_model.get_generation_config()

    models_to_try = [gemini_model.MODEL_NAME]
    for m in getattr(gemini_model, "FALLBACK_MODELS", ["gemini-2.5-flash"]):
        if m not in models_to_try:
            models_to_try.append(m)

    current_model_idx = 0
    response_text = ""

    for retry_count in range(max_retries + 1):
        target_limit = limit_size - (retry_count * 20)
        prompt = text.replace("[limit_size]", str(target_limit))
        current_model = models_to_try[current_model_idx]

        try:
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=config,
            )
            response_text = gemini_model.extract_answer_text(response)
            if not response_text or response_text.strip() == "":
                raise ValueError("レスポンスが空である。")
            if len(response_text) > limit_size:
                raise ValueError(
                    f"レスポンスの文字数が{limit_size}文字を超えている。(実測: {len(response_text)}文字)"
                )
            return response_text

        except ValueError as e:
            print(
                f"文字数または空レスポンスによるリトライ。試行: {retry_count}/{max_retries} (モデル: {current_model})\n"
                f"{e}\n{response_text}"
            )
            if retry_count < max_retries:
                time.sleep(3)
        except Exception as e:
            error_msg = str(e)
            is_server_error = (
                "500" in error_msg or "INTERNAL" in error_msg or
                "503" in error_msg or "UNAVAILABLE" in error_msg
            )
            print(
                f"APIエラーが発生した。リトライ回数: {retry_count}/{max_retries} (モデル: {current_model})\n"
                f"エラータイプ: {type(e).__name__}\nエラーメッセージ: {e}"
            )

            # サーバーエラー（500/503等）でフォールバックモデルが残っている場合は切り替え
            if is_server_error and (current_model_idx + 1) < len(models_to_try):
                current_model_idx += 1
                next_model = models_to_try[current_model_idx]
                print(f"モデルをフォールバックモデル '{next_model}' に切り替えて再試行する...")
                time.sleep(2)
                continue

            if retry_count < max_retries:
                wait_time = min(5 * (2 ** retry_count), 30)
                print(f"{wait_time}秒待機中...")
                time.sleep(wait_time)

    print("最大リトライ回数に達した。")
    if not response_text or response_text.strip() == "":
        return None
    return remove_last_sentence(response_text)

