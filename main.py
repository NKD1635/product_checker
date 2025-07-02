import requests
import os
import json

def send_test_message():
    """LINEに「test」というメッセージを送信する"""
    # GitHubのSecretsからアクセストークンを読み込み
    token = os.environ.get("CHANNEL_ACCESS_TOKEN")
    if not token:
        print("エラー: 環境変数 CHANNEL_ACCESS_TOKEN が設定されていません。")
        return

    # LINE Messaging APIのエンドポイントとヘッダー
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
    }
    
    # 送信するメッセージの本体（ペイロード）
    payload = {
        "messages": [{"type": "text", "text": "test"}]
    }

    try:
        # メッセージを送信
        print("LINEへテストメッセージを送信します...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # エラーチェック
        print("メッセージの送信に成功しました！")

    except requests.exceptions.RequestException as e:
        print(f"メッセージの送信に失敗しました: {e}")
        # エラーレスポンスの内容を表示
        if e.response:
            print(f"エラー内容: {e.response.text}")

if __name__ == "__main__":
    send_test_message()
