# Markets Trending to Bluesky

Markets Trending to Blueskyは、市場の指標値を取得して動向を要約し、Blueskyに投稿するアプリケーションです。  
このアプリケーションは、投資家や市場分析家が迅速に市場のトレンドや変動を把握するために開発されました。

## 関連記事

- [Webスクレイピング×生成AI×SNSで新しい価値が生まれる？すべて無料でBOTを作った話](https://note.com/aegisfleet/n/nc8362f717cd9)

## 特徴

- 様々な市場の指標値を自動取得
- 取得した指標値を基に市場の動向を要約
- 要約をBlueskyに自動投稿

このリポジトリで実行された結果はBlueskyの [デイリーマーケットトレンド](https://bsky.app/profile/dailymarkettrends.bsky.social) に投稿されます。

## インストール

このプロジェクトをローカル環境で動かすには、次の手順を実行してください。

```bash
git clone https://github.com/yourusername/markets-trending-to-bluesky.git
cd markets-trending-to-bluesky
pip install -r requirements.txt
```

## 使用方法

アプリケーションを実行するには、以下のコマンドを使用します。

```
python main.py <ユーザーハンドル> <パスワード> <モード>
```

### モードの種類

- nikkei：日経の指標値の要約を投稿します。
- kabutan：株探の記事の要約を投稿します。
- minkabu：みんかぶの記事の要約を投稿します。

## 技術要素

このアプリケーションは以下の技術を使用しています。

- Python: メインのプログラミング言語
- Pandas: データ分析と処理
- requests: HTTPリクエスト
- g4f: GPTのクライアントライブラリ
- atproto: BlueskyのAPIクライアント

また、開発には以下を使用しています。

- [gpt4free](https://github.com/xtekky/gpt4free): 生成AIを無料で利用するためのライブラリ
- [リートン](https://wrtn.jp/): コード生成やテキスト生成に利用しているAIサービス
- [AWS CodeWhisperer](https://aws.amazon.com/jp/codewhisperer/): コード生成に使用しているAIツール

## マスコット

リートンで生成したマスコット画像。  
名前はまだ無い。

<img src="images\mascot.png" width="50%">
