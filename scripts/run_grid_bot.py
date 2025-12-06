"""
網格交易機器人啟動程式
使用 config/grid_config_example.py 中的配置
支援 Telegram 通知功能
"""

import sys
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.grid_trading_bot import GridTradingBot

# 從配置文件導入參數
from config.grid_config_example import (
    CONFIG_FILE,
    STOCK_SYMBOL,
    LOWER_PRICE,
    UPPER_PRICE,
    GRID_NUM,
    QUANTITY_PER_GRID,
    CHECK_INTERVAL,
    MAX_CAPITAL,
    MAX_POSITION,
    STOP_LOSS_PRICE,
    TAKE_PROFIT_PRICE,
    # Telegram 設定
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED,
    TELEGRAM_STATUS_INTERVAL
)


def main():
    """主程式"""
    print("=" * 60)
    print("股票網格交易機器人")
    print("=" * 60)

    print(f"\n配置摘要:")
    print(f"  交易配置檔: {CONFIG_FILE}")
    print(f"  股票代號: {STOCK_SYMBOL}")
    print(f"  價格區間: {LOWER_PRICE} ~ {UPPER_PRICE}")
    print(f"  網格數量: {GRID_NUM}")
    print(f"  每格數量: {QUANTITY_PER_GRID} 張")
    print(f"  檢查間隔: {CHECK_INTERVAL} 秒")
    if MAX_CAPITAL:
        print(f"  最大本金: ${MAX_CAPITAL:,.0f}")
    if MAX_POSITION:
        print(f"  最大持倉: {MAX_POSITION} 張")
    if STOP_LOSS_PRICE:
        print(f"  停損價格: {STOP_LOSS_PRICE}")
    if TAKE_PROFIT_PRICE:
        print(f"  停利價格: {TAKE_PROFIT_PRICE}")

    # Telegram 設定摘要
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_ENABLED:
        print(f"\n  Telegram 通知: 已啟用")
        print(f"  狀態報告間隔: {TELEGRAM_STATUS_INTERVAL} 秒")
    else:
        print(f"\n  Telegram 通知: 未啟用")

    # 初始化機器人
    try:
        print(f"\n正在初始化機器人...")

        # 日誌檔案名稱（包含股票代號）
        log_file = f"trading_{STOCK_SYMBOL}.log"

        bot = GridTradingBot(
            config_file=CONFIG_FILE,
            log_file=log_file,
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            telegram_enabled=TELEGRAM_ENABLED
        )

        # 設置網格
        bot.setup_grid(
            symbol=STOCK_SYMBOL,
            lower_price=LOWER_PRICE,
            upper_price=UPPER_PRICE,
            grid_num=GRID_NUM,
            quantity_per_grid=QUANTITY_PER_GRID,
            max_capital=MAX_CAPITAL,
            max_position=MAX_POSITION,
            stop_loss_price=STOP_LOSS_PRICE,
            take_profit_price=TAKE_PROFIT_PRICE
        )

        # 啟動機器人
        print(f"\n按 Ctrl+C 可隨時停止機器人\n")
        print(f"日誌檔案: {log_file}\n")
        bot.run(
            check_interval=CHECK_INTERVAL,
            status_report_interval=TELEGRAM_STATUS_INTERVAL
        )

    except KeyboardInterrupt:
        print("\n\n機器人已被使用者停止")
    except Exception as e:
        print(f"\n發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
