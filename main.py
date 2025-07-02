import requests
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import quote_plus

# --- ★設定項目★ ---
SEARCH_KEYWORD = "Switch"
MIN_PRICE = 100
MAX_PRICE = 100000

# --- プログラム本体（変更不要） ---
JST = timezone(timedelta(hours=+9), 'JST')

def send_line_message(message):
    token = os.environ.get("CHANNEL_ACCESS_TOKEN")
    if not token:
        print("エラー: 環境変数 CHANNEL_ACCESS_TOKEN が設定されていません。")
        return
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"messages": [{"type": "text", "text": message}]}
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload))
        r.raise_for_status()
        print("LINEへのメッセージ送信に成功しました。")
    except requests.exceptions.RequestException as e:
        print(f"LINEへのメッセージ送信に失敗しました: {e.response.text}")

def check_site(shop_name, url, item_selector, logic_function):
    print(f"【{shop_name}】をチェック中...")
    found_items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36", "Accept-Language": "ja-JP,ja;q=0.9"}
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select(item_selector)
        print(f"  -> {len(items)}件の商品候補を検出。")
        if not items:
            print("  -> 警告: 商品候補が見つかりませんでした。")
        for i, item in enumerate(items):
            print(f"    - {i+1}番目の商品を解析中...")
            found_info = logic_function(item)
            if found_info:
                found_info['shop'] = shop_name
                found_items.append(found_info)
    except requests.exceptions.RequestException as e:
        print(f"  -> HTTPエラーが発生しました: {e}")
    except Exception as e:
        print(f"  -> その他のエラーが発生しました: {e}")
    print(f"【{shop_name}】のチェック完了。{len(found_items)}件の有効な商品を発見。")
    return found_items

def get_price_from_text(text):
    if not text: return 0
    price_str = re.sub(r'\D', '', text)
    return int(price_str) if price_str else 0

# --- 各サイトの在庫チェックロジック（再修正版） ---

def rakuten_check(item):
    # 「在庫あり」または「予約受付中」のステータスを持つか確認
    status_tag = item.select_one(".inventory_info")
    if status_tag and ("在庫あり" in status_tag.text or "予約受付中" in status_tag.text):
        price_tag = item.select_one(".price_txt")
        if price_tag:
            price = get_price_from_text(price_tag.select_one("em").text)
            print(f"      -> 価格: {price}円")
            if MIN_PRICE <= price <= MAX_PRICE:
                link_tag = item.select_one(".title a")
                if link_tag and link_tag.get('href'):
                    return {'url': link_tag.get('href'), 'price': price}
    return None

def dshopping_check(item):
    if not item.select_one(".c-status--soldout"):
        price_tag = item.select_one(".m-list-items_price")
        if price_tag:
            price = get_price_from_text(price_tag.text)
            print(f"      -> 価格: {price}円")
            if MIN_PRICE <= price <= MAX_PRICE:
                link_tag = item.select_one(".m-list-items_link")
                if link_tag and link_tag.get('href'):
                    return {'url': "https://shopping.dmkt-sp.jp" + link_tag.get('href'), 'price': price}
    return None

def mercari_check(item):
    # メルカリは特に構造が変わりやすいため、より慎重にチェック
    price_tag = item.select_one('[data-testid="price"]')
    if price_tag:
        price = get_price_from_text(price_tag.text)
        print(f"      -> 価格: {price}円")
        if MIN_PRICE <= price <= MAX_PRICE:
            # 商品が売り切れ（SOLD）でないか確認
            if not item.select_one('[data-testid="thumbnail-sold-out-overlay"]'):
                 # item自身がリンクになっていることが多い
                url = item.get('href')
                if url:
                    # 相対パスを絶対パスに変換
                    if url.startswith('/'):
                        url = "https://jp.mercari.com" + url
                    return {'url': url, 'price': price}
    return None

if __name__ == "__main__":
    encoded_keyword = quote_plus(SEARCH_KEYWORD, encoding='utf-8')
    all_found_items = []
    shops_to_check = [
        # {
        #     "name": "Amazon",
        #     "url": f"https://www.amazon.co.jp/s?k={encoded_keyword}",
        #     "item_selector": "div[data-component-type='s-search-result']",
        #     "logic": amazon_check # Amazonはブロックされるため、デフォルトで無効
        # },
        {
            "name": "楽天ブックス",
            "url": f"https://books.rakuten.co.jp/search/dt?sitem={encoded_keyword}&sv=30",
            "item_selector": ".search-result-item",
            "logic": rakuten_check
        },
        {
            "name": "dショッピング",
            "url": f"https://shopping.dmkt-sp.jp/search?keyword={encoded_keyword}",
            "item_selector": "li.m-list-items_item",
            "logic": dshopping_check
        },
        {
            "name": "メルカリ",
            "url": f"https://jp.mercari.com/search?keyword={encoded_keyword}",
            "item_selector": 'a[data-testid="mercari-item-object"]',
            "logic": mercari_check
        },
    ]
    for shop in shops_to_check:
        results = check_site(shop["name"], shop["url"], shop["item_selector"], shop["logic"])
        all_found_items.extend(results)
        
    if all_found_items:
        all_found_items.sort(key=lambda x: x['price'])
        total_count = len(all_found_items)
        message = f"「{SEARCH_KEYWORD}」の販売を検知しました！\n"
        if total_count > 5:
            message += f"（全{total_count}件中、価格が安い5件を表示）\n"
            items_to_show = all_found_items[:5]
        else:
            items_to_show = all_found_items
        for i, item in enumerate(items_to_show):
            message += f"\n【{i+1}】価格: {item['price']:,}円 ({item['shop']})\nURL: {item['url']}\n"
        detection_time = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')
        message += f"\n検知時刻: {detection_time}"
        send_line_message(message)
    else:
        print("最終結果: 条件に合う商品は見つかりませんでした。")
