"""
價格監控服務
每 30 秒檢查所有條件單，符合條件時觸發執行
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor

if TYPE_CHECKING:
    from src.core.trigger_order_manager import TriggerOrderManager

from src.models.trigger_order import TriggerOrder

logger = logging.getLogger('PriceMonitor')

# 執行緒本地儲存 (用於復用 event loop)
_thread_local = threading.local()


class PriceMonitorService:
    """
    價格監控服務

    每隔指定時間檢查所有活躍的條件單，
    當價格滿足條件時觸發執行。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """單例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self,
                 trigger_manager: 'TriggerOrderManager' = None,
                 check_interval: int = 30,
                 max_workers: int = 5):
        """
        初始化監控服務

        Args:
            trigger_manager: 條件單管理器
            check_interval: 檢查間隔 (秒)
            max_workers: 並行查詢股價的執行緒數
        """
        if hasattr(self, '_initialized') and self._initialized:
            # 單例已初始化，僅更新可安全更新的參數
            if trigger_manager is not None:
                self.trigger_manager = trigger_manager
            # 檢查並警告參數差異 (運行中不能更新這些參數)
            if self._running:
                if check_interval != self.check_interval:
                    logger.warning(
                        f"監控服務運行中，無法更新 check_interval "
                        f"(當前: {self.check_interval}, 請求: {check_interval})"
                    )
                if max_workers != self.max_workers:
                    logger.warning(
                        f"監控服務運行中，無法更新 max_workers "
                        f"(當前: {self.max_workers}, 請求: {max_workers})"
                    )
            else:
                # 服務未運行時可以更新參數
                self.check_interval = check_interval
                self.max_workers = max_workers
            return

        self.trigger_manager = trigger_manager
        self.check_interval = check_interval
        self.max_workers = max_workers

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._price_cache: Dict[str, tuple] = {}  # symbol -> (price, timestamp)
        self._cache_ttl = 10  # 快取有效期 (秒)
        self._last_cache_cleanup = datetime.now()

        # 回調函數列表
        self._on_trigger_callbacks: List[Callable[[TriggerOrder, float], None]] = []

        # 統計資訊
        self._stats = {
            'checks': 0,
            'triggers_found': 0,
            'last_check': None,
            'errors': 0
        }

        self._initialized = True

    @property
    def is_running(self) -> bool:
        """是否正在運行"""
        return self._running

    @property
    def stats(self) -> dict:
        """取得統計資訊"""
        return self._stats.copy()

    def start(self):
        """啟動監控服務"""
        if self._running:
            logger.warning("價格監控服務已在運行中")
            return

        if self.trigger_manager is None:
            raise ValueError("未設定 trigger_manager")

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="PriceMonitor"
        )
        self._thread.start()
        logger.info(f"價格監控服務已啟動 (間隔: {self.check_interval}秒)")

    def stop(self):
        """停止監控服務"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("價格監控服務已停止")

    def add_trigger_callback(self, callback: Callable[[TriggerOrder, float], None]):
        """
        註冊觸發回調

        Args:
            callback: 回調函數，接收 (trigger_order, current_price)
        """
        self._on_trigger_callbacks.append(callback)
        logger.debug(f"已註冊觸發回調，目前共 {len(self._on_trigger_callbacks)} 個")

    def remove_trigger_callback(self, callback: Callable):
        """移除觸發回調"""
        if callback in self._on_trigger_callbacks:
            self._on_trigger_callbacks.remove(callback)

    def _monitor_loop(self):
        """監控主迴圈"""
        logger.info("價格監控迴圈已啟動")

        while self._running:
            try:
                self._check_all_triggers()
                self._cleanup_expired_cache()  # 定期清理過期快取
                self._stats['checks'] += 1
                self._stats['last_check'] = datetime.now()
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"監控迴圈錯誤: {e}", exc_info=True)

            # 等待下一次檢查
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("價格監控迴圈已結束")

    def _check_all_triggers(self):
        """檢查所有活躍的條件單"""
        # 取得所有活躍的條件單
        active_triggers = self.trigger_manager.get_all_active_triggers()

        if not active_triggers:
            return

        logger.debug(f"檢查 {len(active_triggers)} 個活躍條件單")

        # 收集需要查詢的股票代號 (去重)
        symbols = list(set(t.symbol for t in active_triggers))

        # 並行查詢股價
        prices = self._fetch_prices(symbols)

        if not prices:
            logger.warning("無法取得任何股價資料")
            return

        # 檢查每個條件單
        for trigger in active_triggers:
            current_price = prices.get(trigger.symbol)

            if current_price is None:
                continue

            # 檢查是否滿足條件
            if trigger.is_condition_met(current_price):
                self._stats['triggers_found'] += 1
                self._handle_trigger_matched(trigger, current_price)

    def _fetch_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        並行查詢多個股票價格

        Args:
            symbols: 股票代號列表

        Returns:
            Dict[symbol, price]
        """
        prices = {}
        now = datetime.now()

        # 檢查快取
        symbols_to_fetch = []
        for symbol in symbols:
            if symbol in self._price_cache:
                cached_price, cached_time = self._price_cache[symbol]
                if (now - cached_time).total_seconds() < self._cache_ttl:
                    prices[symbol] = cached_price
                    continue
            symbols_to_fetch.append(symbol)

        if not symbols_to_fetch:
            return prices

        # 並行查詢
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_single_price, symbol): symbol
                for symbol in symbols_to_fetch
            }

            for future in futures:
                symbol = futures[future]
                try:
                    price = future.result(timeout=15)
                    if price is not None:
                        prices[symbol] = price
                        self._price_cache[symbol] = (price, now)
                except Exception as e:
                    logger.warning(f"查詢 {symbol} 股價失敗: {e}")

        return prices

    def _get_thread_event_loop(self) -> asyncio.AbstractEventLoop:
        """取得當前執行緒的 event loop (復用，避免每次創建)"""
        if not hasattr(_thread_local, 'loop') or _thread_local.loop.is_closed():
            _thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_thread_local.loop)
        return _thread_local.loop

    def _fetch_single_price(self, symbol: str) -> Optional[float]:
        """
        查詢單一股票價格

        Args:
            symbol: 股票代號

        Returns:
            股價或 None
        """
        try:
            from src.core.stock_info import get_stock_quote

            # 使用執行緒本地的 event loop (復用，提升效能)
            loop = self._get_thread_event_loop()
            quote = loop.run_until_complete(get_stock_quote(symbol))
            # 修正: 明確檢查 quote 和 price 是否有效
            # quote.price > 0 才視為有效 (0 通常表示無資料或休市)
            if quote is not None and quote.price is not None and quote.price > 0:
                return quote.price

        except Exception as e:
            logger.debug(f"查詢 {symbol} 股價失敗: {e}")

        return None

    def _handle_trigger_matched(self, trigger: TriggerOrder, current_price: float):
        """處理觸發的條件單"""
        logger.info(
            f"條件單觸發: {trigger.id[:8]}... | {trigger.symbol} | "
            f"條件: {trigger.condition.value} {trigger.trigger_price} | "
            f"當前: {current_price}"
        )

        # 並行執行所有回調 (避免慢回調阻塞其他回調)
        if not self._on_trigger_callbacks:
            return

        def run_callback(callback):
            try:
                callback(trigger, current_price)
            except Exception as e:
                logger.error(f"觸發回調執行錯誤: {e}", exc_info=True)

        with ThreadPoolExecutor(max_workers=len(self._on_trigger_callbacks)) as executor:
            futures = [executor.submit(run_callback, cb) for cb in self._on_trigger_callbacks]
            # 等待所有回調完成 (設定超時避免無限等待)
            for future in futures:
                try:
                    future.result(timeout=60)  # 單個回調最多等待 60 秒
                except Exception as e:
                    logger.error(f"回調執行超時或異常: {e}")

    def check_single_trigger(self, trigger: TriggerOrder) -> Optional[float]:
        """
        手動檢查單一條件單

        Args:
            trigger: 條件單

        Returns:
            當前價格（如果條件滿足）或 None
        """
        price = self._fetch_single_price(trigger.symbol)
        if price and trigger.is_condition_met(price):
            return price
        return None

    def get_cached_price(self, symbol: str) -> Optional[float]:
        """
        取得快取的股價

        Args:
            symbol: 股票代號

        Returns:
            快取的價格或 None
        """
        if symbol in self._price_cache:
            price, cached_time = self._price_cache[symbol]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return price
        return None

    def _cleanup_expired_cache(self):
        """清理過期的價格快取 (防止記憶體累積)"""
        now = datetime.now()

        # 每分鐘清理一次
        if (now - self._last_cache_cleanup).total_seconds() < 60:
            return

        self._last_cache_cleanup = now
        expired_keys = []

        for symbol, (price, cached_time) in self._price_cache.items():
            if (now - cached_time).total_seconds() > self._cache_ttl * 6:  # 過期 6 倍 TTL
                expired_keys.append(symbol)

        for key in expired_keys:
            del self._price_cache[key]

        if expired_keys:
            logger.debug(f"已清理 {len(expired_keys)} 個過期價格快取")

    def clear_cache(self):
        """清除價格快取"""
        self._price_cache.clear()
        logger.debug("價格快取已清除")

    def force_check(self):
        """強制立即執行一次檢查"""
        if not self._running:
            logger.warning("監控服務未運行，無法強制檢查")
            return

        logger.info("強制執行價格檢查")
        try:
            self._check_all_triggers()
            self._stats['checks'] += 1
            self._stats['last_check'] = datetime.now()
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"強制檢查失敗: {e}")


# 全域實例
_monitor_instance: Optional[PriceMonitorService] = None


def get_price_monitor() -> Optional[PriceMonitorService]:
    """取得全域價格監控實例"""
    return _monitor_instance


def init_price_monitor(trigger_manager: 'TriggerOrderManager',
                       check_interval: int = 30) -> PriceMonitorService:
    """
    初始化全域價格監控服務

    Args:
        trigger_manager: 條件單管理器
        check_interval: 檢查間隔

    Returns:
        PriceMonitorService 實例
    """
    global _monitor_instance

    _monitor_instance = PriceMonitorService(
        trigger_manager=trigger_manager,
        check_interval=check_interval
    )

    # 註冊執行回調
    _monitor_instance.add_trigger_callback(trigger_manager.execute_trigger)

    return _monitor_instance
