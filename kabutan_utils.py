import re
import requests
from atproto import Client as BSClient
from g4f.client import Client as GPTClient
from bs4 import BeautifulSoup
import bluesky_utils
import gpt_utils

def get_article_urls_and_titles(url="https://kabutan.jp/info/accessranking/2_1", count=5):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error: Failed to retrieve content from {url}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    article_elements = soup.find_all("td", class_="acrank_title")

    articles = []
    for article_element in article_elements[:count]:
        a_tag = article_element.find("a")
        if a_tag and "href" in a_tag.attrs:
            href = a_tag["href"]
            full_url = f"https://kabutan.jp{href}"
            title = a_tag.text
            articles.append((full_url, title))

    return articles

def remove_newlines(text):
    clean_text = re.sub('\n\s*\n', '\n', text)
    return clean_text

def fetch_article_content(url):
    response = requests.get(url)
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, 'html.parser')
    article_content = soup.find('div', {'id': 'main'}).text.strip()
    article_content = remove_newlines(article_content)
    return article_content[:6000]

def generate_post_text(gpt_client, full_url, title, content, introduction):
    retries = 0
    max_retries = 3
    while retries < max_retries:
        limit_size = 300 - len(introduction) - len(title)
        print(f"limit_size: {limit_size}")
        message = gpt_utils.get_description(
            gpt_client,
            f"この記事で何が伝えたいのか{limit_size}文字以下で3行にまとめて欲しい。"
            "\n回答は日本語で強調文字は使用せず簡素にする。"
            f"\n以下に記事の内容を記載する。\n\n{content}",
            limit_size
        )
        post_text = bluesky_utils.format_message_with_link(
            title, full_url, introduction, message
        )

        if len(post_text.build_text()) < 300:
            return post_text
        retries += 1
        print(f"文字数が300文字を超えています。リトライ回数: {retries}")
    print("300文字以内の文字を生成できませんでした。")
    return None

def post(user_handle, user_password):
    gpt_utils.setup_cookies()

    targets = get_article_urls_and_titles()

    gpt_client = GPTClient()
    bs_client = BSClient()

    for full_url, title in targets:
        print(f"\nURL: {full_url}\nTitle: {title}")

        content = fetch_article_content(full_url)
        post_text = generate_post_text(gpt_client, full_url, title, content, "今日の経済ニュース")
        if not post_text:
            continue

        title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
        print(post_text.build_text(), image_url, sep="\n")

        bluesky_utils.authenticate(bs_client, user_handle, user_password)
        embed_external = bluesky_utils.create_external_embed(
            bs_client, title, description, full_url, image_url
        )
        bluesky_utils.post(bs_client, post_text, embed_external)
