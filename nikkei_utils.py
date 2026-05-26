import datetime
import re
import pytz
import requests
import sys
from atproto import Client as BSClient
from bs4 import BeautifulSoup
import bluesky_utils
import gpt_utils

BASE_URL = "https://www.nikkei.com/marketdata"

# 取得対象指標 (indicator_code, 表示名)
TARGET_INDICATORS = [
    ("NK225", "日経平均"),
    ("DJI", "NYダウ"),
    ("USDJPY", "ドル円"),
    ("IXIC", "NASDAQ"),
    ("SPX", "S&P500"),
]

def _get_build_id():
    """日経マーケットデータページのHTMLからNext.jsのビルドIDを取得する。"""
    response = bluesky_utils.http_get(f"{BASE_URL}/global-overview/")
    response.raise_for_status()
    match = re.search(r'/_next/static/([^/]+)/_buildManifest', response.text)
    if not match:
        raise ValueError("ビルドIDの取得に失敗した")
    return match.group(1)

def _fetch_indicator(build_id, code):
    """指定したindicator_codeの価格データをNext.js _next/dataエンドポイントから取得する。"""
    url = f"{BASE_URL}/_next/data/{build_id}/quote/{code}.json"
    response = bluesky_utils.http_get(url)
    response.raise_for_status()
    data = response.json()
    return data.get("pageProps", {}).get("indicatorValue", {})

def fetch_nikkei_market_data(url="https://www.nikkei.com/marketdata/global-overview/"):
    """日経マーケットデータページから主要指標の価格データを取得する。

    Next.js の _next/data エンドポイントを利用してリアルタイム価格を取得する。
    返り値は各指標の「名称: 値 (変動幅), 更新時間: xx:xx」形式の文字列を改行で連結したもの。
    データが取得できない場合は None を返す。
    """
    try:
        build_id = _get_build_id()
    except Exception as e:
        print(f"ビルドIDの取得に失敗した: {e}")
        return None

    index_data = []
    for code, display_name in TARGET_INDICATORS:
        try:
            iv = _fetch_indicator(build_id, code)
            value = iv.get("value", "")
            diff = iv.get("diff", "")
            diff_percent = iv.get("diffPercent", "")
            time_str = iv.get("time", "")

            change_str = f"{diff} ({diff_percent}%)" if diff_percent else diff
            index_data.append(
                f"{display_name}: {value} ({change_str}), 更新時間: {time_str}"
            )
        except Exception as e:
            print(f"{code} のデータ取得に失敗した: {e}")

    if not index_data:
        return None

    return "\n".join(index_data)

def generate_post_text(api_key, full_url, introduction):
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(jst)
    created_at = now.strftime('%Y/%m/%d %H:%M')
    created_day = now.strftime('%d')

    content = fetch_nikkei_market_data(full_url)
    retries = 0
    max_retries = 3
    while retries < max_retries:
        limit_size = 300 - len(introduction) - len(created_at) - 10
        print(f"limit_size: {limit_size}")
        message = gpt_utils.get_description(
            api_key,
            f"これから与えるデータから分かることを具体的な価格やポイントを使用して3行にまとめて欲しい。\n"
            "回答は強調文字は使用せず、更新時間の情報は不要である。\n"
            f"なるべく{created_day}日に更新された値を紹介し、{created_day}日に更新されていない項目は省略する。\n"
            "必ず[limit_size]文字以下にする。\n"
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

def post(user_handle, user_password, api_key):
    bs_client = BSClient()

    full_url = "https://www.nikkei.com/marketdata/global-overview/"
    print(f"\nURL: {full_url}")

    post_text = generate_post_text(api_key, full_url, "今日の市場動向")
    if not post_text:
        sys.exit(1)

    title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
    print(post_text.build_text(), image_url, sep="\n")

    auth_client = bluesky_utils.authenticate(bs_client, user_handle, user_password)
    embed_external = bluesky_utils.create_external_embed(
        auth_client, title, description, full_url, image_url
    )
    bluesky_utils.post(auth_client, post_text, embed_external)
