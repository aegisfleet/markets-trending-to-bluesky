import sys
from atproto import Client as BSClient
from g4f.client import Client as GPTClient

import nikkei_utils
import bluesky_utils
import gpt_utils
import datetime
import pytz

def print_usage_and_exit():
    print("使用法: python main.py <ユーザーハンドル> <パスワード>")
    sys.exit(1)

def main():
    if len(sys.argv) != 3:
        print_usage_and_exit()

    user_handle, user_password = sys.argv[1], sys.argv[2]

    gpt_utils.setup_cookies()

    gpt_client = GPTClient()
    bs_client = BSClient()

    full_url = "https://www.nikkei.com/markets/worldidx/"
    body_text = nikkei_utils.fetch_nikkei_index(full_url)
    print(body_text)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)

    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    created_at = now.strftime('%Y/%m/%d %H:%M')

    introduction = "今日の市場動向"
    limit_size = 300 - len(introduction) - len(created_at) - 5
    print (f"limit_size: {limit_size}")

    retries = 0
    max_retries = 3
    while retries < max_retries:
        message = gpt_utils.get_description(
            gpt_client, 
            f"今は{created_at}である。これから与えるデータから分かることを"
            f"更新時間が新しいものを対象に{limit_size}文字以下で3行にまとめて欲しい。\n"
            "回答は日本語で強調文字は使用せず簡素にする。\n"
            f"以下にデータを記載する。\n\n{body_text}",
            limit_size
        )
        post_text = bluesky_utils.format_message(
            f"{created_at}時点", introduction, message
        )

        if len(post_text.build_text()) < 300:
            break

        retries += 1
        print(f"文字数が300文字を超えています。リトライ回数: {retries}")

    if retries == max_retries and len(post_text.build_text()) >= 300:
        print("300文字以内の文字を生成できませんでした。")
        sys.exit(1)

    print(post_text.build_text(), image_url, sep="\n")

    bluesky_utils.authenticate(bs_client, user_handle, user_password)
    embed_external = bluesky_utils.create_external_embed(
        bs_client, title, description, full_url, image_url
    )
    bluesky_utils.post(bs_client, post_text, embed_external)

if __name__ == "__main__":
    main()
