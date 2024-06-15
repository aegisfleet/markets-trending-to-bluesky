import sys
import nikkei_utils
import article_utils

def print_usage_and_exit():
    print("使用法: python main.py <BlueSkyのユーザーハンドル> <BlueSkyのパスワード> <GeminiのAPIキー> <モード>")
    sys.exit(1)

def main():
    if len(sys.argv) != 5:
        print_usage_and_exit()

    user_handle, user_password, api_key, mode = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    if mode not in ["nikkei", "kabutan", "minkabu"]:
        print_usage_and_exit()

    if mode == "nikkei":
        nikkei_utils.post(user_handle, user_password, api_key)
    elif mode == "kabutan":
        config_kabutan = {
            "url": "https://kabutan.jp/info/accessranking/2_1",
            "count": 5,
            "base_url": "https://kabutan.jp",
            "container_tag": {"name": "td", "class_": "acrank_title"},
            "title_box_tag": {"name": "", "class_": ""},
            "href_prefix": "",
            "introduction": "今日の経済ニュース"
        }
        article_utils.post(user_handle, user_password, api_key, config_kabutan)
    elif mode == "minkabu":
        config_minkabu = {
            "url": "https://minkabu.jp/news/search?category=popular_recently",
            "count": 5,
            "base_url": "https://minkabu.jp",
            "container_tag": {"name": "div", "class_": "md_index_article"},
            "title_box_tag": {"name": "div", "class_": "title_box"},
            "href_prefix": "",
            "introduction": "今日の経済ニュース"
        }
        article_utils.post(user_handle, user_password, api_key, config_minkabu)

if __name__ == "__main__":
    main()
