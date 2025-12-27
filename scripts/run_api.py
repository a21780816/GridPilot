#!/usr/bin/env python3
"""
條件單 REST API 啟動程式
"""

import os
import sys
import logging
import signal
from pathlib import Path
from configparser import ConfigParser

import uvicorn

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.user_manager import UserManager
from src.core.trigger_order_manager import TriggerOrderManager
from src.core.price_monitor import PriceMonitorService
from src.storage import JsonStorage
from src.api import create_app


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
            logging.FileHandler('api.log', encoding='utf-8')
        ]
    )
    logger = logging.getLogger('Main')

    print("=" * 60)
    print("條件單交易 REST API")
    print("=" * 60)

    # 載入設定
    config = load_config()

    # 優先從設定檔讀取，其次從環境變數
    if config and config.has_option('Telegram', 'BotToken'):
        TELEGRAM_BOT_TOKEN = config.get('Telegram', 'BotToken')
    else:
        TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN':
        print("警告: TELEGRAM_BOT_TOKEN 未設定，條件單觸發時將無法發送通知")
        TELEGRAM_BOT_TOKEN = None

    # 讀取其他設定
    users_dir = './users'
    api_host = '0.0.0.0'
    api_port = 8000
    debug = False

    if config:
        if config.has_option('Server', 'UsersDir'):
            users_dir = config.get('Server', 'UsersDir')
        if config.has_option('API', 'Host'):
            api_host = config.get('API', 'Host')
        if config.has_option('API', 'Port'):
            api_port = config.getint('API', 'Port')
        if config.has_option('API', 'Debug'):
            debug = config.getboolean('API', 'Debug')

    print(f"用戶資料目錄: {users_dir}")
    print(f"API 服務: http://{api_host}:{api_port}")
    print(f"API 文件: http://{api_host}:{api_port}/docs")

    # 初始化管理器
    user_manager = UserManager(base_dir=users_dir)

    # 初始化儲存層
    storage = JsonStorage(base_dir=users_dir)

    # 初始化條件單管理器
    trigger_manager = TriggerOrderManager(
        storage=storage,
        user_manager=user_manager,
        telegram_token=TELEGRAM_BOT_TOKEN
    )

    # 初始化價格監控服務
    price_monitor = PriceMonitorService(
        trigger_manager=trigger_manager,
        check_interval=30  # 每 30 秒檢查
    )

    # 建立 FastAPI 應用
    app = create_app(
        user_manager=user_manager,
        trigger_manager=trigger_manager,
        debug=debug
    )

    # 處理關閉信號
    def shutdown(signum, frame):
        print("\n正在關閉...")
        price_monitor.stop()
        trigger_manager.cleanup_all_brokers()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 啟動價格監控服務
    print("\n啟動價格監控服務...")
    price_monitor.start()
    print("價格監控服務已啟動 (每 30 秒檢查)")

    # 啟動 API 服務
    print("\nAPI 服務啟動中...")
    print("按 Ctrl+C 停止\n")

    try:
        uvicorn.run(
            app,
            host=api_host,
            port=api_port,
            log_level="info" if debug else "warning"
        )
    except Exception as e:
        logger.error(f"API 執行錯誤: {e}")
        price_monitor.stop()
        trigger_manager.cleanup_all_brokers()
        sys.exit(1)


if __name__ == "__main__":
    main()
