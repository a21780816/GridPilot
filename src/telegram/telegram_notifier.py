"""
Telegram 通知模組
用於發送交易通知到 Telegram
"""

import requests
import logging
from datetime import datetime


class TelegramNotifier:
    """Telegram 通知器"""

    def __init__(self, bot_token, chat_id, enabled=True):
        """
        初始化 Telegram 通知器

        Args:
            bot_token: Telegram Bot Token (從 @BotFather 取得)
            chat_id: 接收訊息的 Chat ID (可以是個人或群組)
            enabled: 是否啟用通知
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger('TelegramNotifier')

    def send_message(self, message, parse_mode='HTML'):
        """
        發送訊息到 Telegram

        Args:
            message: 要發送的訊息內容
            parse_mode: 解析模式 ('HTML' 或 'Markdown')

        Returns:
            bool: 是否發送成功
        """
        if not self.enabled:
            return True

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }

            response = requests.post(url, data=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                self.logger.debug(f"Telegram 訊息發送成功")
                return True
            else:
                self.logger.error(f"Telegram 訊息發送失敗: {result}")
                return False

        except Exception as e:
            self.logger.error(f"Telegram 發送錯誤: {e}")
            return False

    def send_startup_message(self, symbol, lower_price, upper_price, grid_num, quantity_per_grid):
        """
        發送機器人啟動通知

        Args:
            symbol: 股票代號
            lower_price: 網格下限
            upper_price: 網格上限
            grid_num: 網格數量
            quantity_per_grid: 每格交易量
        """
        message = f"""
🤖 <b>網格交易機器人已啟動</b>

📊 <b>交易設定</b>
• 股票代號: <code>{symbol}</code>
• 價格區間: {lower_price} ~ {upper_price}
• 網格數量: {grid_num}
• 每格數量: {quantity_per_grid} 張

⏰ 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_shutdown_message(self, reason="使用者停止"):
        """
        發送機器人停止通知

        Args:
            reason: 停止原因
        """
        message = f"""
🛑 <b>網格交易機器人已停止</b>

📝 停止原因: {reason}
⏰ 停止時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_buy_order_message(self, symbol, price, quantity, order_no):
        """
        發送買單通知

        Args:
            symbol: 股票代號
            price: 買入價格
            quantity: 買入數量
            order_no: 委託序號
        """
        message = f"""
📈 <b>買單已送出</b>

• 股票: <code>{symbol}</code>
• 價格: {price}
• 數量: {quantity} 張
• 委託序號: <code>{order_no}</code>
• 時間: {datetime.now().strftime('%H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_sell_order_message(self, symbol, price, quantity, order_no):
        """
        發送賣單通知

        Args:
            symbol: 股票代號
            price: 賣出價格
            quantity: 賣出數量
            order_no: 委託序號
        """
        message = f"""
📉 <b>賣單已送出</b>

• 股票: <code>{symbol}</code>
• 價格: {price}
• 數量: {quantity} 張
• 委託序號: <code>{order_no}</code>
• 時間: {datetime.now().strftime('%H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_order_filled_message(self, symbol, side, price, quantity):
        """
        發送訂單成交通知

        Args:
            symbol: 股票代號
            side: 買/賣
            price: 成交價格
            quantity: 成交數量
        """
        emoji = "✅" if side == "買" else "💰"
        message = f"""
{emoji} <b>訂單已成交</b>

• 股票: <code>{symbol}</code>
• 方向: {side}
• 價格: {price}
• 數量: {quantity} 張
• 時間: {datetime.now().strftime('%H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_stop_loss_message(self, symbol, current_price, stop_loss_price):
        """
        發送停損通知

        Args:
            symbol: 股票代號
            current_price: 當前價格
            stop_loss_price: 停損價格
        """
        message = f"""
🚨 <b>觸發停損！</b>

• 股票: <code>{symbol}</code>
• 當前價格: {current_price}
• 停損價格: {stop_loss_price}
• 時間: {datetime.now().strftime('%H:%M:%S')}

⚠️ 機器人已停止交易
        """
        return self.send_message(message.strip())

    def send_take_profit_message(self, symbol, current_price, take_profit_price):
        """
        發送停利通知

        Args:
            symbol: 股票代號
            current_price: 當前價格
            take_profit_price: 停利價格
        """
        message = f"""
🎉 <b>觸發停利！</b>

• 股票: <code>{symbol}</code>
• 當前價格: {current_price}
• 停利價格: {take_profit_price}
• 時間: {datetime.now().strftime('%H:%M:%S')}

✨ 機器人已停止交易
        """
        return self.send_message(message.strip())

    def send_status_message(self, symbol, current_price, position_qty, avg_price,
                            unrealized_pnl, pending_buys, filled_buys,
                            pending_sells, filled_sells):
        """
        發送狀態報告

        Args:
            symbol: 股票代號
            current_price: 當前價格
            position_qty: 持倉數量
            avg_price: 成本均價
            unrealized_pnl: 未實現損益
            pending_buys: 委託中買單數
            filled_buys: 已成交買單數
            pending_sells: 委託中賣單數
            filled_sells: 已成交賣單數
        """
        # 判斷損益狀態
        pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
        pnl_sign = "+" if unrealized_pnl >= 0 else ""

        message = f"""
📊 <b>狀態報告</b>

<b>股票資訊</b>
• 代號: <code>{symbol}</code>
• 當前價格: {current_price}

<b>持倉狀態</b>
• 持倉數量: {position_qty} 張
• 成本均價: {avg_price}
• 未實現損益: {pnl_emoji} {pnl_sign}{unrealized_pnl:,.0f}

<b>訂單統計</b>
• 買單: {pending_buys} 委託中 / {filled_buys} 已成交
• 賣單: {pending_sells} 委託中 / {filled_sells} 已成交

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_error_message(self, error_msg):
        """
        發送錯誤通知

        Args:
            error_msg: 錯誤訊息
        """
        message = f"""
❌ <b>發生錯誤</b>

{error_msg}

⏰ {datetime.now().strftime('%H:%M:%S')}
        """
        return self.send_message(message.strip())

    def test_connection(self):
        """
        測試 Telegram 連線

        Returns:
            bool: 連線是否成功
        """
        message = f"""
✅ <b>Telegram 連線測試成功！</b>

Bot 已準備就緒，可以接收交易通知。
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())


if __name__ == "__main__":
    # 測試用
    print("Telegram 通知模組測試")
    print("=" * 50)
    print("請在 config/grid_config_example.py 中設定:")
    print("  TELEGRAM_BOT_TOKEN = 'your_bot_token'")
    print("  TELEGRAM_CHAT_ID = 'your_chat_id'")
    print()
    print("取得方式:")
    print("1. 在 Telegram 搜尋 @BotFather")
    print("2. 發送 /newbot 建立機器人")
    print("3. 取得 Bot Token")
    print("4. 在 Telegram 搜尋 @userinfobot")
    print("5. 發送任意訊息取得 Chat ID")
