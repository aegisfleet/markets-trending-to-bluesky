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
    message = gpt_utils.get_description(
        gpt_client, 
        f"今は{created_at}である。これから与えるデータから分かることを"
        "更新時間が新しいものを対象に250文字以下で3行にまとめて欲しい。\n"
        "回答は日本語で強調文字は使用せず簡素にする。\n"
        f"以下にデータを記載する。\n\n{body_text}"
    )
    print(message)

    post_text = bluesky_utils.format_message(
        f"{created_at}時点", "今日の市場動向", message
    )
    print(post_text.build_text(), image_url, sep="\n")

    bluesky_utils.authenticate(bs_client, user_handle, user_password)
    embed_external = bluesky_utils.create_external_embed(
        bs_client, title, description, full_url, image_url
    )
    bluesky_utils.post(bs_client, post_text, embed_external)

if __name__ == "__main__":
    main()
