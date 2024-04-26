import sys
from atproto import Client as BSClient
from g4f.client import Client as GPTClient
import bluesky_utils
import gpt_utils
import nikkei_utils
import datetime
import pytz

config = {
    "utils_module": nikkei_utils,
    "fetch_index_function": "fetch_nikkei_index",
    "introduction": "今日の市場動向",
    "base_url": "https://www.nikkei.com/markets/worldidx/"
}

def print_usage_and_exit():
    print("使用法: python main.py <ユーザーハンドル> <パスワード>")
    sys.exit(1)

def generate_post_text(gpt_client, full_url, introduction):
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    created_at = now.strftime('%Y/%m/%d %H:%M')

    content = getattr(config["utils_module"], config["fetch_index_function"])(full_url)
    retries = 0
    max_retries = 3
    while retries < max_retries:
        limit_size = 300 - len(introduction) - len(created_at) - 10
        print(f"limit_size: {limit_size}")
        message = gpt_utils.get_description(
            gpt_client,
            f"今は{created_at}である。\nこれから与えるデータから分かることを"
            f"更新時間が新しいものを対象に{limit_size}文字以下で3行にまとめて欲しい。\n"
            "回答は強調文字は使用せず、更新時間の情報は不要である。\n"
            "具体的な数字を使用して日経平均/ドル・円を中心に更新された値について紹介する。\n"
            f"以下にデータを記載する。\n\n{content}",
            limit_size
        )
        post_text = bluesky_utils.format_message(
            f"{created_at}時点", introduction, message
        )

        if len(post_text.build_text()) < 300:
            return post_text
        retries += 1
        print(f"文字数が300文字を超えています。リトライ回数: {retries}")
    print("300文字以内の文字を生成できませんでした。")
    return None

def main():
    if len(sys.argv) != 3:
        print_usage_and_exit()

    user_handle, user_password = sys.argv[1], sys.argv[2]
    gpt_utils.setup_cookies()

    gpt_client = GPTClient()
    bs_client = BSClient()

    full_url = config["base_url"]
    print(f"\nURL: {full_url}")

    post_text = generate_post_text(gpt_client, full_url, config["introduction"])
    if not post_text:
        sys.exit(1)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
    print(post_text.build_text(), image_url, sep="\n")

    bluesky_utils.authenticate(bs_client, user_handle, user_password)
    embed_external = bluesky_utils.create_external_embed(
        bs_client, title, description, full_url, image_url
    )
    bluesky_utils.post(bs_client, post_text, embed_external)

if __name__ == "__main__":
    main()
