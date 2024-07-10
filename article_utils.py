import re
import requests
from atproto import Client as BSClient
from bs4 import BeautifulSoup
import artifact_utils
import bluesky_utils
import gpt_utils

def get_articles(config):
    url = config.get("url", "")
    count = config.get("count", 5)
    base_url = config.get("base_url", "")
    container_tag = config.get("container_tag", {"name": "div", "class_": ""})
    title_box_tag = config.get("title_box_tag", {"name": "div", "class_": ""})
    href_prefix = config.get("href_prefix", "")

    previous_articles = artifact_utils.load_previous_results()
    response = requests.get(url)
    if response is None or response.text is None:
        print("Failed to fetch the webpage")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    article_elements = soup.find_all(container_tag["name"], class_=container_tag["class_"])

    articles = []
    for article_element in article_elements[:10]:
        if len(articles) >= count:
            break

        title_box = article_element.find(title_box_tag["name"], class_=title_box_tag["class_"]) if title_box_tag["class_"] else None

        if title_box is None:
            title_box = article_element

        a_tag = title_box.find("a")
        if a_tag and "href" in a_tag.attrs:
            href = a_tag["href"]
            full_url = f"{base_url}{href_prefix}{href}"
            if full_url not in previous_articles:
                title = a_tag.get_text().strip()
                articles.append((full_url, title))

    artifact_utils.save_results(articles)
    return articles

def remove_newlines(text):
    clean_text = re.sub('\n\s*\n', '\n', text)
    return clean_text

def fetch_article_content(url):
    response = requests.get(url)
    if response is None:
        print(f"Failed to fetch the article content from {url}")
        return ""
    
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, 'html.parser')
    main_div = soup.find('div', {'id': 'main'})
    if main_div is None:
        print(f"Could not find main content div in {url}")
        return ""
    
    article_content = main_div.text.strip()
    article_content = remove_newlines(article_content)
    return article_content[:6000]

def generate_post_text(api_key, full_url, title, content, introduction):
    retries = 0
    max_retries = 3
    while retries < max_retries:
        limit_size = 300 - len(introduction) - len(title)
        print(f"limit_size: {limit_size}")
        message = gpt_utils.get_description(
            api_key,
            "この記事で何が伝えたいのか[limit_size]文字以下で3行にまとめて欲しい。"
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

def post(user_handle, user_password, api_key, config):
    targets = get_articles(config)

    bs_client = BSClient()

    for full_url, title in targets:
        print(f"\nURL: {full_url}\nTitle: {title}")

        content = fetch_article_content(full_url)
        post_text = generate_post_text(api_key, full_url, title, content, config.get("introduction", ""))
        if not post_text:
            continue

        title, description, image_url = bluesky_utils.fetch_webpage_metadata(full_url)
        print(post_text.build_text(), image_url, sep="\n")

        bluesky_utils.authenticate(bs_client, user_handle, user_password)
        embed_external = bluesky_utils.create_external_embed(
            bs_client, title, description, full_url, image_url
        )
        bluesky_utils.post(bs_client, post_text, embed_external)
