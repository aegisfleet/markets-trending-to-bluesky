import datetime
import pytz
import requests
import sys
from atproto import Client as BSClient
from g4f.client import Client as GPTClient
from bs4 import BeautifulSoup
import bluesky_utils
import gpt_utils

def fetch_nikkei_index(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    tables = soup.find_all("table", class_="cmn-table_style1")
    if not tables:
        return None

    all_index_data = []

    for table in tables:
        rows = table.find_all("tr")

        index_data = []

        for row in rows:
            header = row.find("th")
            columns = row.find_all("td")
            if header and len(columns) >= 3:
                index_name = header.text.strip()
                value = columns[0].text.strip()
                change = columns[1].text.strip()
                update_time = columns[2].text.strip()
                index_data.append(f"{index_name}: {value} ({change}), 更新時間: {update_time}")

        all_index_data.append("\n".join(index_data))

    return "\n\n".join(all_index_data)

def generate_post_text(gpt_client, full_url, introduction):
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    created_at = now.strftime('%Y/%m/%d %H:%M')

    content = fetch_nikkei_index(full_url)
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

def post(user_handle, user_password):
    gpt_utils.setup_cookies()

    gpt_client = GPTClient()
    bs_client = BSClient()

    full_url = "https://www.nikkei.com/markets/worldidx/"
    print(f"\nURL: {full_url}")

    post_text = generate_post_text(gpt_client, full_url, "今日の市場動向")
    if not post_text:
        sys.exit(1)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
    print(post_text.build_text(), image_url, sep="\n")

    bluesky_utils.authenticate(bs_client, user_handle, user_password)
    embed_external = bluesky_utils.create_external_embed(
        bs_client, title, description, full_url, image_url
    )
    bluesky_utils.post(bs_client, post_text, embed_external)
