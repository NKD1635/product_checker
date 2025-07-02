import requests
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import quote_plus
import time

# Seleniumライブラリのインポート
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# --- ★設定項目★ ---
SEARCH_KEYWORD = "Nintendo Switch"
MIN_PRICE = 100
MAX_PRICE = 100000

# --- プログラム本体 ---
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

def get_selenium_driver():
    """SeleniumのWebDriverをセットアップして返す"""
    options = Options()
    options.add_argument("--headless")  # ブラウザ画面を表示しない
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver

def check_site_with_selenium(driver, shop_name, url, item_selector, logic_function):
    """Seleniumでサイトを検索し、条件に合う商品情報のリストを返す"""
    print(f"【{shop_name}】をチェック中...")
    found_items = []
    try:
        driver.get(url)
        # JavaScriptが読み込まれるのを待つ（3秒）
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        items = soup.select(item_selector)
        print(f"  -> {len(items)}件の商品候補を検出。")
        for i, item in enumerate(items):
            print(f"    - {i+1}番目の商品を解析中...")
            found_info = logic_function(item)
            if found_info:
                found_info['shop'] = shop_name
                found_items.append(found_info)
    except Exception as e:
        print(f"  -> エラーが発生しました: {e}")
    print(f"【{shop_name}】のチェック完了。{len(found_items)}件の有効な商品を発見。")
    return found_items

# --- 各サイトの在庫チェックロジック ---
def get_price_from_text(text):
    if not text: return 0
    price_str = re.sub(r'\D', '', text)
    return int(price_str) if price_str else 0

def mercari_check(item):
    price_tag = item.select_one('[data-testid="price"]')
    if price_tag:
        price = get_price_from_text(price_tag.text)
        print(f"      -> 価格: {price}円")
        if MIN_PRICE <= price <= MAX_PRICE:
            if not item.select_one('[data-testid="thumbnail-sold-out-overlay"]'):
                url_tag = item.select_one('a')
                if url_tag and url_tag.get('href'):
                    url = url_tag.get('href')
                    if url.startswith('/'): url = "https://jp.mercari.com" + url
                    return {'url': url, 'price': price}
    else:
        print("      -> 価格タグが見つかりません")
    return None

if __name__ == "__main__":
    encoded_keyword = quote_plus(SEARCH_KEYWORD, encoding='utf-8')
    all_found_items = []
    
    # チェックするショップごとにブラウザを起動・終了する
    # (メルカリに特化)
    mercari_url = f"https://jp.mercari.com/search?keyword={encoded_keyword}"
    mercari_selector = '[data-testid="item-cell"]'
    
    driver = get_selenium_driver()
    try:
        results = check_site_with_selenium(driver, "メルカリ", mercari_url, mercari_selector, mercari_check)
        all_found_items.extend(results)
    finally:
        driver.quit()

    if all_found_items:
        all_found_items.sort(key=lambda x: x['price'])
        # (通知メッセージの作成と送信ロジックは省略)
        message = f"「{SEARCH_KEYWORD}」の販売を検知しました！\n"
        # ... 以下、前回のコードと同じ通知部分 ...
        total_count = len(all_found_items)
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
