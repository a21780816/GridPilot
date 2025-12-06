"""
股票網格交易機器人
使用富果交易 API 和市場價格 API
支援 Telegram 通知功能
"""

import time
import logging
from datetime import datetime
from configparser import ConfigParser
from functools import wraps
from esun_trade.sdk import SDK
from esun_trade.order import OrderObject
from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action
from esun_marketdata import EsunMarketdata
from src.telegram.telegram_notifier import TelegramNotifier


# 設定日誌系統
def setup_logger(name, log_file=None, level=logging.INFO):
    """
    設定日誌記錄器

    Args:
        name: 日誌記錄器名稱
        log_file: 日誌檔案路徑（可選）
        level: 日誌等級
    """
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    # 控制台輸出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 檔案輸出（可選）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """
    錯誤重試裝飾器

    Args:
        max_retries: 最大重試次數
        delay: 初始延遲秒數
        backoff: 延遲倍數
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger('GridBot')
            retries = 0
            current_delay = delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"{func.__name__} 失敗，已達最大重試次數: {e}")
                        raise
                    logger.warning(f"{func.__name__} 失敗，{current_delay}秒後重試 ({retries}/{max_retries}): {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None
        return wrapper
    return decorator


class OrderStatus:
    """訂單狀態常數"""
    PENDING = 'pending'           # 委託中
    PARTIAL_FILLED = 'partial'    # 部分成交
    FILLED = 'filled'             # 全部成交
    CANCELLED = 'cancelled'       # 已取消
    FAILED = 'failed'             # 失敗


class GridTradingBot:
    def __init__(self, config_file='./config/config.simulation.ini', log_file=None,
                 telegram_bot_token=None, telegram_chat_id=None, telegram_enabled=True):
        """
        初始化網格交易機器人

        Args:
            config_file: 交易 API 配置文件路徑（同時用於交易和市場數據）
            log_file: 日誌檔案路徑（可選，如 'trading.log'）
            telegram_bot_token: Telegram Bot Token（可選）
            telegram_chat_id: Telegram Chat ID（可選）
            telegram_enabled: 是否啟用 Telegram 通知
        """
        # 設定日誌
        self.logger = setup_logger('GridBot', log_file)

        # 載入配置
        config = ConfigParser()
        config.read(config_file)

        # 載入交易 SDK
        self.trade_sdk = SDK(config)
        self.trade_sdk.login()
        self.logger.info("交易 SDK 登入成功")

        # 載入市場數據 SDK（使用同一個 config）
        self.market_sdk = EsunMarketdata(config)
        self.market_sdk.login()
        self.stock = self.market_sdk.rest_client.stock
        self.logger.info("市場數據 API 初始化成功")

        # 初始化 Telegram 通知
        self.telegram = None
        if telegram_bot_token and telegram_chat_id:
            self.telegram = TelegramNotifier(
                bot_token=telegram_bot_token,
                chat_id=telegram_chat_id,
                enabled=telegram_enabled
            )
            self.logger.info("Telegram 通知已啟用")
        else:
            self.logger.info("Telegram 通知未設定（跳過）")

        # 網格設定
        self.symbol = None
        self.grid_levels = []
        self.is_running = False

        # 訂單追蹤（訂單號 -> 訂單資訊）
        self.pending_orders = {}  # 委託中的訂單
        self.filled_orders = {}   # 已成交的訂單

        # 風險控制參數
        self.max_capital = None
        self.max_position = None
        self.stop_loss_price = None
        self.take_profit_price = None

        # API 快取
        self._price_cache = None
        self._price_cache_time = None
        self._position_cache = None
        self._position_cache_time = None
        self._cache_ttl = 5  # 快取有效期（秒）

        # 狀態報告設定
        self._last_status_report_time = None
        self._status_report_interval = 3600  # 預設每小時發送一次狀態報告

    def setup_grid(self, symbol, lower_price, upper_price, grid_num, quantity_per_grid,
                   max_capital=None, max_position=None, stop_loss_price=None, take_profit_price=None):
        """
        設置網格參數

        Args:
            symbol: 股票代號
            lower_price: 網格下限價格
            upper_price: 網格上限價格
            grid_num: 網格數量
            quantity_per_grid: 每格交易數量（張）
            max_capital: 最大本金投入（元），None 表示不限制
            max_position: 最大持倉數量（張），None 表示不限制
            stop_loss_price: 停損價格，None 表示不設定
            take_profit_price: 停利價格，None 表示不設定
        """
        self.symbol = symbol
        self.quantity_per_grid = quantity_per_grid

        # 風險控制參數
        self.max_capital = max_capital
        self.max_position = max_position
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price

        # 計算網格間距
        grid_spacing = (upper_price - lower_price) / grid_num

        # 建立網格價位
        self.grid_levels = []
        for i in range(grid_num + 1):
            price = lower_price + (i * grid_spacing)
            self.grid_levels.append({
                'price': round(price, 2),
                'buy_order_no': None,      # 買單委託序號
                'buy_status': None,        # 買單狀態
                'buy_filled_qty': 0,       # 買單已成交數量
                'sell_order_no': None,     # 賣單委託序號
                'sell_status': None,       # 賣單狀態
                'sell_filled_qty': 0,      # 賣單已成交數量
            })

        # 計算所需本金
        max_buy_count = grid_num
        estimated_capital = lower_price * 1000 * quantity_per_grid * max_buy_count

        self.logger.info("=== 網格設定完成 ===")
        self.logger.info(f"股票代號: {symbol}")
        self.logger.info(f"價格區間: {lower_price} ~ {upper_price}")
        self.logger.info(f"網格數量: {grid_num}")
        self.logger.info(f"每格數量: {quantity_per_grid} 張")
        self.logger.info(f"預估所需本金: ${estimated_capital:,.0f}")

        if max_capital:
            self.logger.info(f"最大本金投入: ${max_capital:,.0f}")
            if max_capital < estimated_capital:
                shortage = estimated_capital - max_capital
                self.logger.warning(f"本金不足 ${shortage:,.0f}，可能無法買滿所有網格")

        if max_position:
            self.logger.info(f"最大持倉: {max_position} 張")
        if stop_loss_price:
            self.logger.info(f"停損價格: {stop_loss_price}")
        if take_profit_price:
            self.logger.info(f"停利價格: {take_profit_price}")

        self.logger.info("網格價位:")
        for idx, level in enumerate(self.grid_levels):
            self.logger.info(f"  Level {idx}: {level['price']}")

    def _is_cache_valid(self, cache_time):
        """檢查快取是否有效"""
        if cache_time is None:
            return False
        return (datetime.now() - cache_time).total_seconds() < self._cache_ttl

    @retry_on_failure(max_retries=3, delay=1)
    def get_current_price(self, use_cache=True):
        """
        獲取當前股票價格

        Args:
            use_cache: 是否使用快取
        """
        # 檢查快取
        if use_cache and self._is_cache_valid(self._price_cache_time):
            return self._price_cache

        quote = self.stock.intraday.quote(symbol=self.symbol)
        current_price = quote['closePrice']

        # 更新快取
        self._price_cache = current_price
        self._price_cache_time = datetime.now()

        return current_price

    @retry_on_failure(max_retries=3, delay=1)
    def get_position(self, use_cache=True):
        """
        獲取當前持倉

        Args:
            use_cache: 是否使用快取
        """
        # 檢查快取
        if use_cache and self._is_cache_valid(self._position_cache_time):
            return self._position_cache

        inventories = self.trade_sdk.get_inventories()
        position = None
        for item in inventories:
            if item.get('stock_no') == self.symbol:
                position = item
                break

        # 更新快取
        self._position_cache = position
        self._position_cache_time = datetime.now()

        return position

    def get_confirmed_position(self):
        """
        獲取已確認的持倉數量（用於賣出前檢查）
        強制更新快取以獲取最新資料
        """
        position = self.get_position(use_cache=False)
        if position:
            return position.get('quantity', 0)
        return 0

    @retry_on_failure(max_retries=3, delay=1)
    def get_order_status(self, order_no):
        """
        查詢訂單狀態

        Args:
            order_no: 委託序號

        Returns:
            dict: 訂單狀態資訊
        """
        try:
            orders = self.trade_sdk.get_orders()
            for order in orders:
                if order.get('ord_no') == order_no:
                    # 解析訂單狀態
                    status = order.get('status', '')
                    filled_qty = order.get('filled_qty', 0)
                    order_qty = order.get('quantity', 0)

                    if status == 'cancelled':
                        return {'status': OrderStatus.CANCELLED, 'filled_qty': filled_qty}
                    elif filled_qty >= order_qty:
                        return {'status': OrderStatus.FILLED, 'filled_qty': filled_qty}
                    elif filled_qty > 0:
                        return {'status': OrderStatus.PARTIAL_FILLED, 'filled_qty': filled_qty}
                    else:
                        return {'status': OrderStatus.PENDING, 'filled_qty': 0}

            return None
        except Exception as e:
            self.logger.error(f"查詢訂單狀態失敗: {e}")
            return None

    def update_order_statuses(self):
        """更新所有委託中訂單的狀態"""
        for idx, level in enumerate(self.grid_levels):
            # 更新買單狀態
            if level['buy_order_no'] and level['buy_status'] == OrderStatus.PENDING:
                status_info = self.get_order_status(level['buy_order_no'])
                if status_info:
                    level['buy_status'] = status_info['status']
                    level['buy_filled_qty'] = status_info['filled_qty']

                    if status_info['status'] == OrderStatus.FILLED:
                        self.logger.info(f"Level {idx} 買單已成交: {level['price']}")
                        # 發送 Telegram 通知
                        if self.telegram:
                            self.telegram.send_order_filled_message(
                                self.symbol, "買", level['price'], self.quantity_per_grid
                            )
                    elif status_info['status'] == OrderStatus.CANCELLED:
                        self.logger.warning(f"Level {idx} 買單已取消: {level['price']}")
                        level['buy_order_no'] = None  # 清除訂單號，允許重新下單

            # 更新賣單狀態
            if level['sell_order_no'] and level['sell_status'] == OrderStatus.PENDING:
                status_info = self.get_order_status(level['sell_order_no'])
                if status_info:
                    level['sell_status'] = status_info['status']
                    level['sell_filled_qty'] = status_info['filled_qty']

                    if status_info['status'] == OrderStatus.FILLED:
                        self.logger.info(f"Level {idx} 賣單已成交: {level['price']}")
                        # 發送 Telegram 通知
                        if self.telegram:
                            self.telegram.send_order_filled_message(
                                self.symbol, "賣", level['price'], self.quantity_per_grid
                            )
                        # 賣單成交後，重置買單狀態允許再次買入
                        level['buy_order_no'] = None
                        level['buy_status'] = None
                        level['buy_filled_qty'] = 0
                    elif status_info['status'] == OrderStatus.CANCELLED:
                        self.logger.warning(f"Level {idx} 賣單已取消: {level['price']}")
                        level['sell_order_no'] = None

    @retry_on_failure(max_retries=2, delay=0.5)
    def place_buy_order(self, price, quantity):
        """
        下買單

        Args:
            price: 買入價格
            quantity: 買入數量（張）

        Returns:
            str: 委託序號，失敗返回 None
        """
        order = OrderObject(
            stock_no=self.symbol,
            buy_sell=Action.Buy,
            quantity=quantity,
            price=price,
            price_flag=PriceFlag.Limit,
            ap_code=APCode.Common,
            bs_flag=BSFlag.ROD,
            trade=Trade.Cash
        )

        result = self.trade_sdk.place_order(order)
        order_no = result.get('ord_no')

        if order_no:
            self.logger.info(f"買單已送出: {self.symbol} @ {price}, 數量: {quantity} 張, 委託序號: {order_no}")
            # 發送 Telegram 通知
            if self.telegram:
                self.telegram.send_buy_order_message(self.symbol, price, quantity, order_no)
            return order_no
        else:
            self.logger.error(f"買單失敗: {result}")
            return None

    @retry_on_failure(max_retries=2, delay=0.5)
    def place_sell_order(self, price, quantity):
        """
        下賣單

        Args:
            price: 賣出價格
            quantity: 賣出數量（張）

        Returns:
            str: 委託序號，失敗返回 None
        """
        order = OrderObject(
            stock_no=self.symbol,
            buy_sell=Action.Sell,
            quantity=quantity,
            price=price,
            price_flag=PriceFlag.Limit,
            ap_code=APCode.Common,
            bs_flag=BSFlag.ROD,
            trade=Trade.Cash
        )

        result = self.trade_sdk.place_order(order)
        order_no = result.get('ord_no')

        if order_no:
            self.logger.info(f"賣單已送出: {self.symbol} @ {price}, 數量: {quantity} 張, 委託序號: {order_no}")
            # 發送 Telegram 通知
            if self.telegram:
                self.telegram.send_sell_order_message(self.symbol, price, quantity, order_no)
            return order_no
        else:
            self.logger.error(f"賣單失敗: {result}")
            return None

    def check_grid_signals(self, current_price):
        """
        檢查網格交易信號

        Args:
            current_price: 當前價格
        """
        # 檢查停損停利
        if self.stop_loss_price and current_price <= self.stop_loss_price:
            self.logger.warning(f"觸發停損: 當前價格 {current_price} <= 停損價 {self.stop_loss_price}")
            self.logger.info("機器人已停止交易")
            if self.telegram:
                self.telegram.send_stop_loss_message(self.symbol, current_price, self.stop_loss_price)
            self.is_running = False
            return

        if self.take_profit_price and current_price >= self.take_profit_price:
            self.logger.info(f"觸發停利: 當前價格 {current_price} >= 停利價 {self.take_profit_price}")
            self.logger.info("機器人已停止交易")
            if self.telegram:
                self.telegram.send_take_profit_message(self.symbol, current_price, self.take_profit_price)
            self.is_running = False
            return

        # 先更新所有訂單狀態
        self.update_order_statuses()

        # 計算當前持倉和成本（用於風險控制）
        current_position = 0
        current_cost = 0

        if self.max_position or self.max_capital:
            position_info = self.get_position()
            if position_info:
                current_position = position_info.get('quantity', 0)
                avg_price = position_info.get('avg_price', 0)
                current_cost = current_position * 1000 * avg_price

        for idx, level in enumerate(self.grid_levels):
            grid_price = level['price']

            # 檢查買入信號
            # 條件：價格下跌到網格點，且沒有進行中或已成交的買單
            can_buy = (
                level['buy_order_no'] is None or
                level['buy_status'] in [OrderStatus.CANCELLED, OrderStatus.FAILED]
            )

            if current_price <= grid_price and can_buy:
                # 檢查是否超過最大持倉
                if self.max_position and current_position >= self.max_position:
                    self.logger.debug(f"已達最大持倉 {self.max_position} 張，跳過買入")
                    continue

                # 檢查是否超過最大本金
                if self.max_capital:
                    buy_cost = grid_price * 1000 * self.quantity_per_grid
                    total_cost = current_cost + buy_cost
                    if total_cost > self.max_capital:
                        self.logger.debug(f"超過最大本金限制 ${self.max_capital:,.0f}，跳過買入")
                        continue

                self.logger.info(f"觸發買入信號: 價格 {current_price} <= 網格 {grid_price}")
                order_no = self.place_buy_order(grid_price, self.quantity_per_grid)

                if order_no:
                    level['buy_order_no'] = order_no
                    level['buy_status'] = OrderStatus.PENDING
                    level['buy_filled_qty'] = 0
                    # 更新預估持倉和成本
                    current_position += self.quantity_per_grid
                    current_cost += grid_price * 1000 * self.quantity_per_grid

            # 檢查賣出信號
            # 條件：價格上漲到網格點，買單已成交，且沒有進行中的賣單
            can_sell = (
                level['buy_status'] == OrderStatus.FILLED and
                (level['sell_order_no'] is None or
                 level['sell_status'] in [OrderStatus.CANCELLED, OrderStatus.FAILED])
            )

            if current_price >= grid_price and can_sell:
                # 賣出前確認實際持倉，防止超賣
                confirmed_position = self.get_confirmed_position()

                if confirmed_position < self.quantity_per_grid:
                    self.logger.warning(
                        f"持倉不足，無法賣出: 需要 {self.quantity_per_grid} 張，"
                        f"實際持倉 {confirmed_position} 張"
                    )
                    continue

                self.logger.info(f"觸發賣出信號: 價格 {current_price} >= 網格 {grid_price}")
                order_no = self.place_sell_order(grid_price, self.quantity_per_grid)

                if order_no:
                    level['sell_order_no'] = order_no
                    level['sell_status'] = OrderStatus.PENDING
                    level['sell_filled_qty'] = 0

    def print_status(self, current_price, check_position=True):
        """打印當前狀態"""
        self.logger.info("=" * 50)
        self.logger.info(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"股票: {self.symbol}")
        self.logger.info(f"當前價格: {current_price}")

        if check_position:
            position = self.get_position()
            if position:
                self.logger.info(f"持倉數量: {position.get('quantity', 0)} 張")
                self.logger.info(f"成本價格: {position.get('avg_price', 0)}")
                self.logger.info(f"未實現損益: {position.get('unrealized_pnl', 0)}")
            else:
                self.logger.info("持倉數量: 0 張")

        # 統計訂單狀態
        pending_buys = sum(1 for l in self.grid_levels if l['buy_status'] == OrderStatus.PENDING)
        filled_buys = sum(1 for l in self.grid_levels if l['buy_status'] == OrderStatus.FILLED)
        pending_sells = sum(1 for l in self.grid_levels if l['sell_status'] == OrderStatus.PENDING)
        filled_sells = sum(1 for l in self.grid_levels if l['sell_status'] == OrderStatus.FILLED)

        self.logger.info(f"買單: {pending_buys} 委託中 / {filled_buys} 已成交")
        self.logger.info(f"賣單: {pending_sells} 委託中 / {filled_sells} 已成交")
        self.logger.info("=" * 50)

    def run(self, check_interval=60, status_report_interval=3600):
        """
        啟動網格交易機器人

        Args:
            check_interval: 檢查間隔（秒）
            status_report_interval: Telegram 狀態報告間隔（秒），預設 3600（1小時）
        """
        if not self.symbol or not self.grid_levels:
            raise Exception("請先使用 setup_grid() 設置網格參數")

        self.is_running = True
        self._status_report_interval = status_report_interval
        self._last_status_report_time = datetime.now()

        self.logger.info("=" * 50)
        self.logger.info("網格交易機器人已啟動")
        self.logger.info(f"檢查間隔: {check_interval} 秒")
        self.logger.info("按 Ctrl+C 停止")
        self.logger.info("=" * 50)

        # 發送 Telegram 啟動通知
        if self.telegram:
            lower_price = self.grid_levels[0]['price']
            upper_price = self.grid_levels[-1]['price']
            grid_num = len(self.grid_levels) - 1
            self.telegram.send_startup_message(
                self.symbol, lower_price, upper_price, grid_num, self.quantity_per_grid
            )

        iteration = 0
        try:
            while self.is_running:
                iteration += 1

                try:
                    # 獲取當前價格
                    current_price = self.get_current_price(use_cache=False)

                    if current_price:
                        # 檢查網格信號
                        self.check_grid_signals(current_price)

                        # 每 5 次檢查才查詢一次持倉（減少 API 呼叫）
                        check_position = (iteration % 5 == 0)
                        self.print_status(current_price, check_position=check_position)

                        # 發送定時 Telegram 狀態報告
                        self._send_periodic_status_report(current_price)

                except Exception as e:
                    self.logger.error(f"執行週期發生錯誤: {e}")
                    # 發送錯誤通知
                    if self.telegram:
                        self.telegram.send_error_message(str(e))
                    # 繼續執行，不中斷機器人

                # 等待下次檢查
                time.sleep(check_interval)

        except KeyboardInterrupt:
            self.logger.info("機器人已被使用者停止")
            # 發送 Telegram 停止通知
            if self.telegram:
                self.telegram.send_shutdown_message("使用者停止 (Ctrl+C)")
            self.is_running = False

    def _send_periodic_status_report(self, current_price):
        """發送定時狀態報告到 Telegram"""
        if not self.telegram:
            return

        now = datetime.now()
        elapsed = (now - self._last_status_report_time).total_seconds()

        if elapsed >= self._status_report_interval:
            # 獲取持倉資訊
            position = self.get_position()
            position_qty = position.get('quantity', 0) if position else 0
            avg_price = position.get('avg_price', 0) if position else 0
            unrealized_pnl = position.get('unrealized_pnl', 0) if position else 0

            # 統計訂單
            pending_buys = sum(1 for l in self.grid_levels if l['buy_status'] == OrderStatus.PENDING)
            filled_buys = sum(1 for l in self.grid_levels if l['buy_status'] == OrderStatus.FILLED)
            pending_sells = sum(1 for l in self.grid_levels if l['sell_status'] == OrderStatus.PENDING)
            filled_sells = sum(1 for l in self.grid_levels if l['sell_status'] == OrderStatus.FILLED)

            self.telegram.send_status_message(
                self.symbol, current_price, position_qty, avg_price,
                unrealized_pnl, pending_buys, filled_buys, pending_sells, filled_sells
            )

            self._last_status_report_time = now

    def stop(self):
        """停止機器人"""
        self.is_running = False
        self.logger.info("網格交易機器人已停止")
        # 發送 Telegram 停止通知
        if self.telegram:
            self.telegram.send_shutdown_message("程式停止")


if __name__ == "__main__":
    # 使用範例
    print("股票網格交易機器人")
    print("=" * 50)

    # 配置參數
    STOCK_SYMBOL = "2330"  # 台積電
    LOWER_PRICE = 500.0    # 網格下限
    UPPER_PRICE = 600.0    # 網格上限
    GRID_NUM = 10          # 10 個網格
    QUANTITY = 1           # 每格 1 張
    CHECK_INTERVAL = 60    # 每 60 秒檢查一次

    # 初始化機器人（可選：指定日誌檔案）
    bot = GridTradingBot(
        config_file='./config/config.simulation.ini',
        log_file='trading.log'  # 日誌同時輸出到檔案
    )

    # 設置網格
    bot.setup_grid(
        symbol=STOCK_SYMBOL,
        lower_price=LOWER_PRICE,
        upper_price=UPPER_PRICE,
        grid_num=GRID_NUM,
        quantity_per_grid=QUANTITY
    )

    # 啟動機器人
    bot.run(check_interval=CHECK_INTERVAL)
