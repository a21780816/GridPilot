#!/usr/bin/env python3
"""
Telegram 交易機器人啟動程式
整合多用戶管理和交易功能
"""

import os
import sys
import logging
import signal
from pathlib import Path
from configparser import ConfigParser

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.user_manager import UserManager
from src.core.bot_manager import BotManager
from src.telegram.telegram_bot import TradingBot


def load_config():
    """載入設定檔"""
    config_path = project_root / 'config' / 'telegram.ini'

    if not config_path.exists():
        return None

    config = ConfigParser()
    config.read(config_path, encoding='utf-8')
    return config


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

    # 載入設定
    config = load_config()

    # 優先從設定檔讀取，其次從環境變數
    if config and config.has_option('Telegram', 'BotToken'):
        TELEGRAM_BOT_TOKEN = config.get('Telegram', 'BotToken')
    else:
        TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN':
        print("錯誤: TELEGRAM_BOT_TOKEN 未設定")
        print()
        print("請選擇以下方式之一設定 Bot Token:")
        print("1. 複製 config/telegram.example.ini 為 config/telegram.ini 並填入 Token")
        print("2. 設定環境變數: export TELEGRAM_BOT_TOKEN='your_token'")
        sys.exit(1)

    # 讀取其他設定
    max_users = 10
    users_dir = './users'

    if config:
        if config.has_option('Server', 'MaxUsers'):
            max_users = config.getint('Server', 'MaxUsers')
        if config.has_option('Server', 'UsersDir'):
            users_dir = config.get('Server', 'UsersDir')

    print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-5:]}")
    print(f"最大用戶數: {max_users}")
    print(f"用戶資料目錄: {users_dir}")

    # 初始化管理器
    user_manager = UserManager(base_dir=users_dir)
    bot_manager = BotManager(
        user_manager=user_manager,
        telegram_token=TELEGRAM_BOT_TOKEN
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
