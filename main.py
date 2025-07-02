import requests
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import re

# --- ★設定項目★ ---
# 1. 検索したい商品名（キーワード）を設定
SEARCH_KEYWORD = "Nintendo Switch 2"

# 2. 検索したい価格帯を設定
MIN_PRICE = 50000
MAX_PRICE = 100000


# --- プログラム本体（ここから下は変更不要） ---

# 日本時間のタイムゾーンを定義
JST = timezone(timedelta(hours=+9), 'JST')

def send_line_message(message):
    """LINE Messaging APIを使って、メッセージを送信する"""
    token = os.environ.get("CHANNEL_ACCESS_TOKEN")
    if not token:
        print("エラー: 環境変数 CHANNEL_ACCESS_TOKEN が設定されていません。")
        return

    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
    }
    payload = {"messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("LINEへのメッセージ送信に成功しました。")
    except requests.exceptions.RequestException as e:
        print(f"LINEへのメッセージ送信に失敗しました: {e.response.text}")


def check_site(shop_name, url, item_selector, logic_function):
    """指定されたサイトを検索し、在庫があれば通知"""
    print(f"【{shop_name}】をチェック中...")
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        items = soup.select(item_selector)
        print(f"  -> {len(items)}件の商品候補を検出。")
        for item in items:
            # 各サイトのロジックで在庫と価格を判定
            found_url = logic_function(item)
            if found_url:
                print(f"  -> 条件に合う在庫を発見！")
                detection_time = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')
                message = (
                    f"{SEARCH_KEYWORD}の販売を検知しました！\n\n"
                    f"URL: {found_url}\n"
                    f"検知時刻: {detection_time}"
                )
                send_line_message(message)
                return True # 検知したことを伝える
    except Exception as e:
        print(f"  -> エラーが発生しました: {e}")
    
    print(f"  -> 条件に合う在庫なし")
    return False

# --- 各サイトの在庫チェックロジック ---
# ※サイトのHTML構造が変更されると、動作しなくなる可能性があります。

def get_price_from_text(text):
    """文字列から数値（価格）のみを抽出する"""
    price_str = re.sub(r'\D', '', text) # 数字以外をすべて削除
    return int(price_str) if price_str else 0

def rakuten_check(item):
    """楽天ブックスのアイテムをチェック"""
    # 在庫判定：「ご注文できない」表示がない
    if not item.select_one(".rb-item-list__item__cart--unavailable"):
        price_tag = item.select_one(".rb-item-list__item__price, .price-box .price")
        if price_tag:
            price = get_price_from_text(price_tag.text)
            if MIN_PRICE <= price <= MAX_PRICE:
                link_tag = item.select_one("a")
                if link_tag and link_tag.get('href'):
                    return link_tag.get('href')
    return None

def mercari_check(item):
    """メルカリのアイテムをチェック"""
    price_tag = item.select_one('mer-price, .price') # セレクタは変わりやすい
    if price_tag:
        # メルカリの価格は 'price' 属性に含まれていることが多い
        price_text = price_tag.get('price', price_tag.text)
        price = get_price_from_text(price_text)
        if MIN_PRICE <= price <= MAX_PRICE:
            link_tag = item.select_one("a")
            if link_tag and link_tag.get('href'):
                # メルカリのリンクはドメインからの相対パスなので結合する
                return "https://jp.mercari.com" + link_tag.get('href')
    return None


if __name__ == "__main__":
    # チェックするショップのリスト
    shops_to_check = [
        {
            "name": "楽天ブックス",
            "url": f"https://books.rakuten.co.jp/search?sitem={SEARCH_KEYWORD}",
            "item_selector": ".rb-item-list__item", # 商品一つ一つを囲む要素
            "logic": rakuten_check
        },
        {
            "name": "メルカリ",
            "url": f"https://jp.mercari.com/search?keyword={SEARCH_KEYWORD}&status=on_sale",
            "item_selector": 'li[data-testid^="item-cell-"]', # 商品一つ一つを囲む要素
            "logic": mercari_check
        },
    ]

    for shop in shops_to_check:
        # 在庫を検知したら、他のショップはチェックせずに終了
        if check_site(shop["name"], shop["url"], shop["item_selector"], shop["logic"]):
            break
