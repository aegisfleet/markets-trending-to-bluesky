import sys
from atproto import Client as BSClient
from g4f.client import Client as GPTClient

import nikkei_utils
import bluesky_utils
import gpt_utils

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

    full_url="https://www.nikkei.com/markets/worldidx/"
    body_text = nikkei_utils.fetch_nikkei_index(full_url)
    print(body_text)

    message = gpt_utils.get_description(gpt_client, body_text)
    print(message)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
    print(title, description, image_url, sep="\n")

    bluesky_utils.authenticate(bs_client, user_handle, user_password)
    post_text = bluesky_utils.format_message_with_link(title, full_url, "今日の市場動向", message)
    embed_external = bluesky_utils.create_external_embed(bs_client, title, description, full_url, image_url)
    bluesky_utils.post(bs_client, post_text, embed_external)

if __name__ == "__main__":
    main()
