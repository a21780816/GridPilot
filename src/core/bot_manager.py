"""
多用戶多標的交易機器人管理器
管理多個用戶的多個標的交易機器人實例
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from src.core.user_manager import UserManager
from src.brokers import get_broker
from src.telegram.telegram_notifier import TelegramNotifier

logger = logging.getLogger('BotManager')


@dataclass
class GridLevel:
    """網格層級"""
    price: float
    buy_order_no: Optional[str] = None
    buy_status: Optional[str] = None
    buy_filled_qty: int = 0
    sell_order_no: Optional[str] = None
    sell_status: Optional[str] = None
    sell_filled_qty: int = 0


@dataclass
class GridBotInstance:
    """單一標的網格機器人實例"""
    chat_id: str
    symbol: str
    broker: object
    broker_name: str
    notifier: TelegramNotifier
    grid_config: Dict
    grid_levels: List[GridLevel] = field(default_factory=list)
    is_running: bool = False
    thread: Optional[threading.Thread] = None
    last_price: float = 0
    iteration: int = 0
    started_at: Optional[str] = None


class BotManager:
    """多用戶多標的交易機器人管理器"""

    def __init__(self, user_manager: UserManager, telegram_token: str, max_grids: int = 50):
        """
        初始化

        Args:
            user_manager: 用戶管理器
            telegram_token: Telegram Bot Token
            max_grids: 最大同時運行網格數
        """
        self.user_manager = user_manager
        self.telegram_token = telegram_token
        self.max_grids = max_grids
        # key: "{chat_id}_{symbol}"
        self._bots: Dict[str, GridBotInstance] = {}
        # 每個券商只需一個連線實例
        # key: "{chat_id}_{broker_name}"
        self._broker_instances: Dict[str, object] = {}
        self._lock = threading.Lock()

    def _get_bot_key(self, chat_id, symbol: str) -> str:
        """取得機器人 key"""
        return f"{chat_id}_{symbol}"

    def _get_broker_key(self, chat_id, broker_name: str) -> str:
        """取得券商 key"""
        return f"{chat_id}_{broker_name}"

    def _get_or_create_broker(self, chat_id, broker_name: str) -> Optional[object]:
        """取得或建立券商實例"""
        broker_key = self._get_broker_key(chat_id, broker_name)

        if broker_key in self._broker_instances:
            broker = self._broker_instances[broker_key]
            if broker.is_logged_in():
                return broker

        # 取得券商設定
        broker_config = self.user_manager.get_broker_config(chat_id, broker_name)
        if not broker_config:
            logger.error(f"券商設定不存在: {chat_id}/{broker_name}")
            return None

        try:
            broker = get_broker(broker_name, broker_config)
            if not broker.login():
                logger.error(f"券商登入失敗: {chat_id}/{broker_name}")
                return None

            self._broker_instances[broker_key] = broker
            logger.info(f"券商連線成功: {chat_id}/{broker_name}")
            return broker

        except Exception as e:
            logger.error(f"建立券商實例失敗: {chat_id}/{broker_name} - {e}")
            return None

    def start_grid(self, chat_id, symbol: str) -> tuple:
        """
        啟動標的的網格交易

        Args:
            chat_id: 用戶 Chat ID
            symbol: 股票代號

        Returns:
            tuple: (成功與否, 訊息)
        """
        chat_id = str(chat_id)
        bot_key = self._get_bot_key(chat_id, symbol)

        with self._lock:
            # 檢查是否已在運行
            if bot_key in self._bots and self._bots[bot_key].is_running:
                return True, f"{symbol} 已在運行中"

            # 檢查運行數量
            running_count = sum(1 for b in self._bots.values() if b.is_running)
            if running_count >= self.max_grids:
                return False, f"已達最大網格數 {self.max_grids}"

            # 取得網格設定
            grid_config = self.user_manager.get_grid_config(chat_id, symbol)
            if not grid_config:
                return False, f"找不到 {symbol} 的網格設定"

            broker_name = grid_config.get('broker')
            if not broker_name:
                return False, f"{symbol} 未設定券商"

            # 取得券商實例
            broker = self._get_or_create_broker(chat_id, broker_name)
            if not broker:
                return False, f"無法連接券商 {broker_name}"

            try:
                # 建立通知器
                notifier = TelegramNotifier(
                    bot_token=self.telegram_token,
                    chat_id=chat_id,
                    enabled=True
                )

                # 建立機器人實例
                bot_instance = GridBotInstance(
                    chat_id=chat_id,
                    symbol=symbol,
                    broker=broker,
                    broker_name=broker_name,
                    notifier=notifier,
                    grid_config=grid_config,
                    started_at=datetime.now().isoformat()
                )

                # 設置網格
                self._setup_grid(bot_instance)

                # 啟動交易執行緒
                bot_instance.is_running = True
                bot_instance.thread = threading.Thread(
                    target=self._run_trading_loop,
                    args=(bot_instance,),
                    daemon=True,
                    name=f"Grid-{chat_id}-{symbol}"
                )
                bot_instance.thread.start()

                self._bots[bot_key] = bot_instance

                # 更新 user_manager 狀態
                self.user_manager.set_grid_running_status(chat_id, symbol, True)

                # 發送啟動通知
                notifier.send_startup_message(
                    symbol,
                    grid_config['lower_price'],
                    grid_config['upper_price'],
                    grid_config['grid_num'],
                    grid_config['quantity_per_grid']
                )

                logger.info(f"網格啟動成功: {chat_id}/{symbol}")
                return True, f"{symbol} 網格交易已啟動"

            except Exception as e:
                logger.error(f"啟動網格失敗: {chat_id}/{symbol} - {e}")
                return False, f"啟動失敗: {e}"

    def stop_grid(self, chat_id, symbol: str) -> tuple:
        """
        停止標的的網格交易

        Args:
            chat_id: 用戶 Chat ID
            symbol: 股票代號

        Returns:
            tuple: (成功與否, 訊息)
        """
        chat_id = str(chat_id)
        bot_key = self._get_bot_key(chat_id, symbol)

        with self._lock:
            if bot_key not in self._bots:
                return False, f"{symbol} 未在運行"

            bot = self._bots[bot_key]
            bot.is_running = False

            # 等待執行緒結束
            if bot.thread and bot.thread.is_alive():
                bot.thread.join(timeout=5)

            # 發送停止通知
            bot.notifier.send_shutdown_message("用戶停止")

            # 更新 user_manager 狀態
            self.user_manager.set_grid_running_status(chat_id, symbol, False)

            del self._bots[bot_key]

            # 檢查是否還有其他網格使用此券商，沒有則登出
            self._cleanup_broker_if_unused(chat_id, bot.broker_name)

            logger.info(f"網格停止成功: {chat_id}/{symbol}")
            return True, f"{symbol} 網格交易已停止"

    def _cleanup_broker_if_unused(self, chat_id, broker_name: str):
        """如果券商沒有被其他網格使用則登出"""
        broker_key = self._get_broker_key(chat_id, broker_name)

        # 檢查是否還有使用此券商的網格
        in_use = any(
            b.broker_name == broker_name and b.chat_id == chat_id
            for b in self._bots.values()
            if b.is_running
        )

        if not in_use and broker_key in self._broker_instances:
            try:
                self._broker_instances[broker_key].logout()
                del self._broker_instances[broker_key]
                logger.info(f"券商已登出: {chat_id}/{broker_name}")
            except Exception as e:
                logger.warning(f"登出券商失敗: {e}")

    def get_grid_status(self, chat_id, symbol: str) -> Optional[Dict]:
        """
        取得標的網格狀態

        Args:
            chat_id: 用戶 Chat ID
            symbol: 股票代號

        Returns:
            Dict: 狀態資訊
        """
        chat_id = str(chat_id)
        bot_key = self._get_bot_key(chat_id, symbol)

        if bot_key not in self._bots:
            return None

        bot = self._bots[bot_key]
        config = bot.grid_config

        # 取得持倉
        try:
            position = bot.broker.get_position(symbol)
        except:
            position = None

        # 統計訂單
        pending_buys = sum(1 for l in bot.grid_levels if l.buy_status == 'pending')
        filled_buys = sum(1 for l in bot.grid_levels if l.buy_status == 'filled')
        pending_sells = sum(1 for l in bot.grid_levels if l.sell_status == 'pending')
        filled_sells = sum(1 for l in bot.grid_levels if l.sell_status == 'filled')

        return {
            'symbol': symbol,
            'broker': bot.broker_name,
            'current_price': bot.last_price,
            'lower_price': config['lower_price'],
            'upper_price': config['upper_price'],
            'grid_num': config['grid_num'],
            'position_qty': position.quantity if position else 0,
            'avg_price': position.avg_price if position else 0,
            'unrealized_pnl': position.unrealized_pnl if position else 0,
            'pending_buys': pending_buys,
            'filled_buys': filled_buys,
            'pending_sells': pending_sells,
            'filled_sells': filled_sells,
            'is_running': bot.is_running,
            'started_at': bot.started_at,
            'iteration': bot.iteration
        }

    def get_user_running_grids(self, chat_id) -> List[Dict]:
        """取得用戶所有運行中的網格狀態"""
        chat_id = str(chat_id)
        results = []

        for bot_key, bot in self._bots.items():
            if bot.chat_id == chat_id and bot.is_running:
                status = self.get_grid_status(chat_id, bot.symbol)
                if status:
                    results.append(status)

        return results

    def stop_user_all_grids(self, chat_id) -> int:
        """停止用戶所有網格"""
        chat_id = str(chat_id)
        stopped = 0

        # 找出所有屬於此用戶的網格
        user_bots = [
            bot.symbol for bot in self._bots.values()
            if bot.chat_id == chat_id and bot.is_running
        ]

        for symbol in user_bots:
            success, _ = self.stop_grid(chat_id, symbol)
            if success:
                stopped += 1

        return stopped

    def _setup_grid(self, bot: GridBotInstance):
        """設置網格"""
        config = bot.grid_config
        lower = config['lower_price']
        upper = config['upper_price']
        num = config['grid_num']

        spacing = (upper - lower) / num
        bot.grid_levels = []

        for i in range(num + 1):
            price = round(lower + i * spacing, 2)
            bot.grid_levels.append(GridLevel(price=price))

        logger.info(f"網格設置完成: {bot.chat_id}/{bot.symbol} - {lower} ~ {upper}, {num} 格")

    def _run_trading_loop(self, bot: GridBotInstance):
        """交易主迴圈"""
        config = bot.grid_config
        symbol = bot.symbol
        quantity = config['quantity_per_grid']
        interval = config.get('check_interval', 60)

        logger.info(f"交易迴圈開始: {bot.chat_id}/{symbol}")

        while bot.is_running:
            try:
                bot.iteration += 1

                # 取得當前價格
                price = bot.broker.get_current_price(symbol)
                if price is None:
                    time.sleep(interval)
                    continue

                bot.last_price = price

                # 更新訂單狀態
                self._update_order_statuses(bot)

                # 檢查交易信號
                self._check_grid_signals(bot, price)

                # 檢查停損停利
                self._check_stop_conditions(bot, price)

                # 每 30 次檢查發送狀態（約 30 分鐘一次）
                if bot.iteration % 30 == 0:
                    self._send_status_report(bot)

            except Exception as e:
                logger.error(f"交易迴圈錯誤: {bot.chat_id}/{symbol} - {e}")
                bot.notifier.send_error_message(f"{symbol}: {e}")

            time.sleep(interval)

        logger.info(f"交易迴圈結束: {bot.chat_id}/{symbol}")

    def _update_order_statuses(self, bot: GridBotInstance):
        """更新訂單狀態"""
        symbol = bot.symbol
        quantity = bot.grid_config['quantity_per_grid']

        for level in bot.grid_levels:
            # 更新買單
            if level.buy_order_no and level.buy_status == 'pending':
                order = bot.broker.get_order_status(level.buy_order_no)
                if order:
                    level.buy_status = order.status
                    level.buy_filled_qty = order.filled_qty

                    if order.status == 'filled':
                        logger.info(f"買單成交: {bot.chat_id}/{symbol} @ {level.price}")
                        bot.notifier.send_order_filled_message(
                            symbol, "買", level.price, quantity
                        )
                    elif order.status == 'cancelled':
                        level.buy_order_no = None

            # 更新賣單
            if level.sell_order_no and level.sell_status == 'pending':
                order = bot.broker.get_order_status(level.sell_order_no)
                if order:
                    level.sell_status = order.status
                    level.sell_filled_qty = order.filled_qty

                    if order.status == 'filled':
                        logger.info(f"賣單成交: {bot.chat_id}/{symbol} @ {level.price}")
                        bot.notifier.send_order_filled_message(
                            symbol, "賣", level.price, quantity
                        )
                        # 重置買單狀態，準備下一輪
                        level.buy_order_no = None
                        level.buy_status = None
                        level.buy_filled_qty = 0
                    elif order.status == 'cancelled':
                        level.sell_order_no = None

    def _check_grid_signals(self, bot: GridBotInstance, current_price: float):
        """檢查網格交易信號"""
        symbol = bot.symbol
        quantity = bot.grid_config['quantity_per_grid']

        for level in bot.grid_levels:
            # 檢查買入信號
            can_buy = (
                level.buy_order_no is None or
                level.buy_status in ['cancelled', 'failed', None]
            )

            if current_price <= level.price and can_buy:
                result = bot.broker.place_buy_order(symbol, level.price, quantity)
                if result.success:
                    level.buy_order_no = result.order_no
                    level.buy_status = 'pending'
                    logger.info(f"買單送出: {bot.chat_id}/{symbol} @ {level.price}")
                    bot.notifier.send_buy_order_message(
                        symbol, level.price, quantity, result.order_no
                    )

            # 檢查賣出信號
            can_sell = (
                level.buy_status == 'filled' and
                (level.sell_order_no is None or
                 level.sell_status in ['cancelled', 'failed', None])
            )

            if current_price >= level.price and can_sell:
                # 確認持倉
                position = bot.broker.get_position(symbol)
                if position and position.quantity >= quantity:
                    result = bot.broker.place_sell_order(symbol, level.price, quantity)
                    if result.success:
                        level.sell_order_no = result.order_no
                        level.sell_status = 'pending'
                        logger.info(f"賣單送出: {bot.chat_id}/{symbol} @ {level.price}")
                        bot.notifier.send_sell_order_message(
                            symbol, level.price, quantity, result.order_no
                        )

    def _check_stop_conditions(self, bot: GridBotInstance, current_price: float):
        """檢查停損停利條件"""
        config = bot.grid_config
        symbol = bot.symbol

        stop_loss = config.get('stop_loss_price')
        take_profit = config.get('take_profit_price')

        if stop_loss and current_price <= stop_loss:
            logger.warning(f"觸發停損: {bot.chat_id}/{symbol} @ {current_price}")
            bot.notifier.send_stop_loss_message(symbol, current_price, stop_loss)
            bot.is_running = False
            self.user_manager.set_grid_running_status(bot.chat_id, symbol, False)

        if take_profit and current_price >= take_profit:
            logger.info(f"觸發停利: {bot.chat_id}/{symbol} @ {current_price}")
            bot.notifier.send_take_profit_message(symbol, current_price, take_profit)
            bot.is_running = False
            self.user_manager.set_grid_running_status(bot.chat_id, symbol, False)

    def _send_status_report(self, bot: GridBotInstance):
        """發送狀態報告"""
        status = self.get_grid_status(bot.chat_id, bot.symbol)
        if status:
            bot.notifier.send_status_message(
                status['symbol'],
                status['current_price'],
                status['position_qty'],
                status['avg_price'],
                status['unrealized_pnl'],
                status['pending_buys'],
                status['filled_buys'],
                status['pending_sells'],
                status['filled_sells']
            )

    def get_running_count(self) -> int:
        """取得運行中的網格數量"""
        return sum(1 for b in self._bots.values() if b.is_running)

    def get_all_running_grids(self) -> List[Dict]:
        """取得所有運行中網格的狀態"""
        results = []
        for bot in self._bots.values():
            if bot.is_running:
                status = self.get_grid_status(bot.chat_id, bot.symbol)
                if status:
                    status['chat_id'] = bot.chat_id
                    results.append(status)
        return results

    def stop_all(self):
        """停止所有網格"""
        for bot_key in list(self._bots.keys()):
            bot = self._bots[bot_key]
            self.stop_grid(bot.chat_id, bot.symbol)

        # 登出所有券商
        for broker_key in list(self._broker_instances.keys()):
            try:
                self._broker_instances[broker_key].logout()
            except:
                pass
        self._broker_instances.clear()
