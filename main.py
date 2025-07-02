import requests
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import quote_plus # URLエンコード用

# --- ★設定項目★ ---
# 1. 検索したい商品名（キーワード）を設定
SEARCH_KEYWORD = "Nintendo Switch 2"

# 2. 検索したい価格帯を設定
MIN_PRICE = 45000
MAX_PRICE = 70000


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
        # ユーザーエージェントを偽装してアクセス
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        items = soup.select(item_selector)
        print(f"  -> {len(items)}件の商品候補を検出。")
        for item in items:
            found_info = logic_function(item)
            if found_info:
                print(f"  -> 条件に合う在庫を発見！ 価格: {found_info['price']}円")
                detection_time = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')
                
                message = (
                    f"{SEARCH_KEYWORD}の販売を検知しました！\n\n"
                    f"価格: {found_info['price']:,}円\n"
                    f"URL: {found_info['url']}\n"
                    f"検知時刻: {detection_time}"
                )
                
                send_line_message(message)
                return True
    except Exception as e:
        print(f"  -> エラーが発生しました: {e}")
    
    print(f"  -> 条件に合う在庫なし")
    return False

# --- 各サイトの在庫チェックロジック ---

def get_price_from_text(text):
    """文字列から数値（価格）のみを抽出する"""
    price_str = re.sub(r'\D', '', text)
    return int(price_str) if price_str else 0

def amazon_check(item):
    """Amazonのアイテムをチェック"""
    # スポンサープロダクトを除外
    if item.select_one('[data-component-type="sp-sponsored-result"]'):
        return None
        
    price_tag = item.select_one('.a-price-whole')
    if price_tag:
        price = get_price_from_text(price_tag.text)
        if MIN_PRICE <= price <= MAX_PRICE:
            link_tag = item.select_one('a.a-link-normal')
            if link_tag and link_tag.get('href'):
                return {'url': "https://www.amazon.co.jp" + link_tag.get('href'), 'price': price}
    return None

def rakuten_check(item):
    """楽天ブックスのアイテムをチェック"""
    if not item.select_one(".rb-item-list__item__cart--unavailable"):
        price_tag = item.select_one(".rb-item-list__item__price, .price-box .price")
        if price_tag:
            price = get_price_from_text(price_tag.text)
            if MIN_PRICE <= price <= MAX_PRICE:
                link_tag = item.select_one("a")
                if link_tag and link_tag.get('href'):
                    return {'url': link_tag.get('href'), 'price': price}
    return None

def dshopping_check(item):
    """dショッピングのアイテムをチェック"""
    # 「在庫なし」の表示がないか確認
    if not item.select_one(".item-preorder-information, .c-icon--stock-none"):
        price_tag = item.select_one(".product-list-item-price-value")
        if price_tag:
            price = get_price_from_text(price_tag.text)
            if MIN_PRICE <= price <= MAX_PRICE:
                link_tag = item.select_one(".product-list-item-link")
                if link_tag and link_tag.get('href'):
                    return {'url': "https://shopping.dmkt-sp.jp" + link_tag.get('href'), 'price': price}
    return None

def mercari_check(item):
    """メルカリのアイテムをチェック"""
    price_tag = item.select_one('mer-price, .price')
    if price_tag:
        price_text = price_tag.get('price', price_tag.text)
        price = get_price_from_text(price_text)
        if MIN_PRICE <= price <= MAX_PRICE:
            link_tag = item.select_one("a")
            if link_tag and link_tag.get('href'):
                return {'url': "https://jp.mercari.com" + link_tag.get('href'), 'price': price}
    return None


if __name__ == "__main__":
    # キーワードをURL用にエンコード
    encoded_keyword = quote_plus(SEARCH_KEYWORD)

    # チェックするショップのリスト
    shops_to_check = [
        {
            "name": "Amazon",
            "url": f"https://www.amazon.co.jp/s?k={encoded_keyword}",
            "item_selector": "[data-component-type='s-search-result']",
            "logic": amazon_check
        },
        {
            "name": "楽天ブックス",
            "url": f"https://books.rakuten.co.jp/search?sitem={encoded_keyword}",
            "item_selector": ".rb-item-list__item",
            "logic": rakuten_check
        },
        {
            "name": "dショッピング",
            "url": f"https://shopping.dmkt-sp.jp/search?keyword={encoded_keyword}",
            "item_selector": ".product-list-item",
            "logic": dshopping_check
        },
        {
            "name": "メルカリ",
            "url": f"https://jp.mercari.com/search?keyword={encoded_keyword}&status=on_sale",
            "item_selector": 'li[data-testid^="item-cell-"]',
            "logic": mercari_check
        },
    ]

    for shop in shops_to_check:
        if check_site(shop["name"], shop["url"], shop["item_selector"], shop["logic"]):
            break
