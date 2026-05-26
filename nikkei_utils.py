import datetime
import re
import pytz
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from atproto import Client as BSClient
import bluesky_utils
import gpt_utils

BASE_URL = "https://www.nikkei.com/marketdata"

def _get_build_id():
    """日経マーケットデータページのHTMLからNext.jsのビルドIDを取得する。"""
    response = bluesky_utils.http_get(f"{BASE_URL}/global-overview/")
    response.raise_for_status()
    match = re.search(r'/_next/static/([^/]+)/_buildManifest', response.text)
    if not match:
        raise ValueError("ビルドIDの取得に失敗した")
    return match.group(1)

def _fetch_indicator_profiles(build_id):
    """global-overview.json から全指標プロフィール一覧を取得する。"""
    url = f"{BASE_URL}/_next/data/{build_id}/global-overview.json"
    response = bluesky_utils.http_get(url)
    response.raise_for_status()
    return response.json().get("pageProps", {}).get("indicatorProfileList", [])

def _fetch_quote(build_id, code, group_name, service_name):
    """指定コードの価格データを取得する。失敗時は None を返す。"""
    url = f"{BASE_URL}/_next/data/{build_id}/quote/{code}.json"
    try:
        response = bluesky_utils.http_get(url)
        response.raise_for_status()
        props = response.json().get("pageProps", {})
        iv = props.get("indicatorValue", {})
        if not iv.get("value"):
            return None
        return {
            "code": code,
            "group_name": group_name,
            "service_name": service_name,
            "value": iv.get("value", ""),
            "diff": iv.get("diff", ""),
            "diff_percent": iv.get("diffPercent", ""),
            "time": iv.get("time", ""),
        }
    except Exception as e:
        print(f"{code} の取得に失敗した: {e}")
        return None

def fetch_nikkei_market_data(url="https://www.nikkei.com/marketdata/global-overview/"):
    """日経マーケットデータページから全指標の価格データを取得する。

    global-overview.json から指標一覧を動的取得し、各指標の quote を並列フェッチする。
    カテゴリごとにグループ化した文字列を返す。取得失敗時は None を返す。
    """
    try:
        build_id = _get_build_id()
    except Exception as e:
        print(f"ビルドIDの取得に失敗した: {e}")
        return None

    try:
        profiles = _fetch_indicator_profiles(build_id)
    except Exception as e:
        print(f"指標一覧の取得に失敗した: {e}")
        return None

    print(f"指標プロフィール取得完了: {len(profiles)} 件")

    # 並列で全指標の価格データを取得
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(
                _fetch_quote,
                build_id,
                p["indicator_code"],
                p["group_name"],
                p["service_name"],
            ): p["indicator_code"]
            for p in profiles
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    if not results:
        return None

    # group_name の登場順を profiles から取得してソート
    group_order = {}
    code_order = {}
    for i, p in enumerate(profiles):
        gname = p["group_name"]
        if gname not in group_order:
            group_order[gname] = len(group_order)
        code_order[p["indicator_code"]] = i

    results.sort(key=lambda x: (
        group_order.get(x["group_name"], 999),
        code_order.get(x["code"], 999),
    ))

    # カテゴリごとに整形
    lines = []
    current_group = None
    for r in results:
        if r["group_name"] != current_group:
            current_group = r["group_name"]
            lines.append(f"\n【{current_group}】")
        change_str = ""
        if r["diff"]:
            pct = f" ({r['diff_percent']}%)" if r["diff_percent"] else ""
            change_str = f" ({r['diff']}{pct})"
        time_str = f", 更新時間: {r['time']}" if r["time"] else ""
        lines.append(f"{r['service_name']}: {r['value']}{change_str}{time_str}")

    return "\n".join(lines).strip()

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
