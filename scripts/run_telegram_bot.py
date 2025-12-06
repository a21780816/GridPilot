#!/usr/bin/env python3
"""
Telegram 交易機器人啟動程式
整合多用戶管理和交易功能
"""

import sys
import logging
import signal
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.user_manager import UserManager
from src.core.bot_manager import BotManager
from src.telegram.telegram_bot import TradingBot


def main():
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('telegram_bot.log', encoding='utf-8')
        ]
    )
    logger = logging.getLogger('Main')

    print("=" * 60)
    print("網格交易 Telegram Bot")
    print("=" * 60)

    # 讀取設定
    try:
        from config.grid_config_example import TELEGRAM_BOT_TOKEN
    except ImportError:
        print("錯誤: 無法讀取設定檔")
        print("請確認 config/grid_config_example.py 存在且包含 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN:
        print("錯誤: TELEGRAM_BOT_TOKEN 未設定")
        print("請在 config/grid_config_example.py 設定 Bot Token")
        sys.exit(1)

    print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-5:]}")

    # 初始化管理器
    user_manager = UserManager(base_dir='./users')
    bot_manager = BotManager(
        user_manager=user_manager,
        telegram_token=TELEGRAM_BOT_TOKEN,
        max_users=10
    )

    # 建立 Telegram Bot
    telegram_bot = TradingBot(
        token=TELEGRAM_BOT_TOKEN,
        user_manager=user_manager,
        bot_manager=bot_manager
    )

    # 處理關閉信號
    def shutdown(signum, frame):
        print("\n正在關閉...")
        bot_manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 啟動 Bot
    print("\nBot 啟動中...")
    print("按 Ctrl+C 停止\n")

    try:
        telegram_bot.run()
    except Exception as e:
        logger.error(f"Bot 執行錯誤: {e}")
        bot_manager.stop_all()
        sys.exit(1)


if __name__ == "__main__":
    main()
