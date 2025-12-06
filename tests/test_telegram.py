"""
Telegram 通知測試腳本
用於測試 Telegram Bot 連線是否正常
"""

import sys
sys.path.append('.')

from telegram_notifier import TelegramNotifier


def main():
    print("=" * 60)
    print("Telegram 通知測試")
    print("=" * 60)

    # 從配置檔讀取設定
    try:
        from config.grid_config_example import (
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID,
            TELEGRAM_ENABLED
        )
    except ImportError:
        print("\n錯誤: 無法讀取配置檔")
        print("請確認 config/grid_config_example.py 存在")
        return

    # 檢查設定
    if not TELEGRAM_BOT_TOKEN:
        print("\n錯誤: TELEGRAM_BOT_TOKEN 未設定")
        print("\n請按照以下步驟設定:")
        print("1. 在 Telegram 搜尋 @BotFather")
        print("2. 發送 /newbot 建立機器人")
        print("3. 複製 Bot Token 到 config/grid_config_example.py")
        return

    if not TELEGRAM_CHAT_ID:
        print("\n錯誤: TELEGRAM_CHAT_ID 未設定")
        print("\n請按照以下步驟設定:")
        print("1. 在 Telegram 搜尋 @userinfobot")
        print("2. 發送任意訊息取得您的 Chat ID")
        print("3. 複製 Chat ID 到 config/grid_config_example.py")
        return

    print(f"\n配置資訊:")
    print(f"  Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-5:]}")
    print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"  啟用狀態: {TELEGRAM_ENABLED}")

    # 建立通知器
    notifier = TelegramNotifier(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        enabled=TELEGRAM_ENABLED
    )

    # 測試連線
    print("\n正在發送測試訊息...")
    success = notifier.test_connection()

    if success:
        print("\n測試成功！請檢查您的 Telegram 是否收到訊息。")
    else:
        print("\n測試失敗！請檢查:")
        print("  1. Bot Token 是否正確")
        print("  2. Chat ID 是否正確")
        print("  3. 是否已經在 Telegram 上與 Bot 開始對話")
        print("     (需要先向 Bot 發送任意訊息)")


if __name__ == "__main__":
    main()
