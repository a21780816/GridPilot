"""
自動偵測 Telegram Chat ID
使用方式：
1. 先在 config/grid_config_example.py 設定 TELEGRAM_BOT_TOKEN
2. 在 Telegram 上向您的 Bot 發送任意訊息
3. 執行此腳本：python3 get_telegram_chat_id.py
"""

import sys
from pathlib import Path

import requests

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_chat_id_from_config():
    """從配置檔讀取 Bot Token"""
    try:
        from config.grid_config_example import TELEGRAM_BOT_TOKEN
        return TELEGRAM_BOT_TOKEN
    except ImportError:
        return None


def get_chat_id_from_input():
    """讓使用者輸入 Bot Token"""
    print("\n請輸入您的 Telegram Bot Token:")
    print("（從 @BotFather 取得，格式如：1234567890:ABCdefGHIjklMNOpqrsTUVwxyz）")
    token = input("> ").strip()
    return token if token else None


def fetch_updates(bot_token):
    """從 Telegram API 取得更新"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        print(f"錯誤: {e}")
        return None


def main():
    print("=" * 60)
    print("Telegram Chat ID 自動偵測工具")
    print("=" * 60)

    # 取得 Bot Token
    bot_token = get_chat_id_from_config()

    if bot_token:
        print(f"\n已從配置檔讀取 Bot Token: {bot_token[:10]}...{bot_token[-5:]}")
    else:
        bot_token = get_chat_id_from_input()

    if not bot_token:
        print("\n錯誤: 未提供 Bot Token")
        return

    # 提示使用者發送訊息
    print("\n" + "=" * 60)
    print("請確認您已經在 Telegram 上向 Bot 發送過訊息！")
    print("（如果還沒有，請先發送任意訊息給您的 Bot）")
    print("=" * 60)
    input("\n按 Enter 繼續偵測...")

    # 取得更新
    print("\n正在從 Telegram API 取得訊息...")
    result = fetch_updates(bot_token)

    if not result:
        print("無法連接 Telegram API")
        return

    if not result.get('ok'):
        print(f"API 錯誤: {result.get('description', '未知錯誤')}")
        print("\n請確認 Bot Token 是否正確")
        return

    updates = result.get('result', [])

    if not updates:
        print("\n未找到任何訊息！")
        print("\n請確認：")
        print("1. 您已經在 Telegram 上向 Bot 發送過訊息")
        print("2. Bot Token 正確")
        print("\n解決方法：")
        print("1. 在 Telegram 搜尋您的 Bot")
        print("2. 點擊 Start 或發送任意訊息")
        print("3. 再次執行此腳本")
        return

    # 解析並顯示所有找到的 Chat ID
    print("\n" + "=" * 60)
    print("找到以下 Chat ID：")
    print("=" * 60)

    seen_chats = {}
    for update in updates:
        message = update.get('message') or update.get('edited_message')
        if message:
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type', 'unknown')
            chat_title = chat.get('title') or chat.get('first_name', '') + ' ' + chat.get('last_name', '')
            chat_title = chat_title.strip()
            username = chat.get('username', '')

            if chat_id and chat_id not in seen_chats:
                seen_chats[chat_id] = {
                    'type': chat_type,
                    'title': chat_title,
                    'username': username
                }

    for chat_id, info in seen_chats.items():
        print(f"\n  Chat ID: {chat_id}")
        print(f"  類型: {info['type']}")
        if info['title']:
            print(f"  名稱: {info['title']}")
        if info['username']:
            print(f"  用戶名: @{info['username']}")

    # 如果只有一個，建議直接使用
    if len(seen_chats) == 1:
        chat_id = list(seen_chats.keys())[0]
        print("\n" + "=" * 60)
        print(f"建議使用的 Chat ID: {chat_id}")
        print("=" * 60)
        print(f"\n請將以下設定加入 config/grid_config_example.py：")
        print(f'\nTELEGRAM_CHAT_ID = "{chat_id}"')
    else:
        print("\n" + "=" * 60)
        print("請選擇要使用的 Chat ID，並加入配置檔")
        print("=" * 60)


if __name__ == "__main__":
    main()
