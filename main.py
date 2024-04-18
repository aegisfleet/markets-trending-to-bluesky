import g4f
import sys
import time
from atproto import Client as BSClient
from g4f.client import Client as GPTClient
from g4f.cookies import set_cookies
from g4f.errors import RateLimitError

import nikkei_utils
import bluesky_utils

def setup_cookies():
    set_cookies(".bing.com", {
        "_U": "cookie value"
    })

def print_usage_and_exit():
    print("使用法: python main.py <ユーザーハンドル> <パスワード>")
    sys.exit(1)

def get_description(gpt_client, text, max_retries=3):
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = gpt_client.chat.completions.create(
                model="gpt-4-turbo",
                provider=g4f.Provider.Bing,
                messages=[{"role": "user", "content": f"これから与えるデータから分かることを250文字以下で3行にまとめて欲しい。\n回答は日本語で強調文字は使用せず簡素にする。\n以下にデータを記載する。\n\n{text}"}],
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            retry_count += 1
            print(f"RateLimitErrorが発生しました。リトライ回数: {retry_count}")
            time.sleep(3)
            continue
    raise Exception("最大リトライ回数に達しました。")

def main():
    if len(sys.argv) != 3:
        print_usage_and_exit()

    user_handle, user_password = sys.argv[1], sys.argv[2]

    setup_cookies()

    gpt_client = GPTClient()
    bs_client = BSClient()

    full_url="https://www.nikkei.com/markets/worldidx/"
    body_text = nikkei_utils.fetch_nikkei_index(full_url)
    print(body_text)

    message = get_description(gpt_client, body_text)
    print(message)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
    print(title, description, image_url, sep="\n")

    embed_external = bluesky_utils.create_external_embed(title, description, full_url)
    post_text = bluesky_utils.format_message_with_link(title, full_url, "今日の市場動向", message)

    bluesky_utils.authenticate_and_post(bs_client, user_handle, user_password, post_text, embed_external)

if __name__ == "__main__":
    main()
