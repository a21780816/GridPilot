"""
條件單管理器
管理條件單的 CRUD 操作和執行
"""

import logging
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from src.models.trigger_order import TriggerOrder
from src.models.enums import TriggerCondition, OrderType, OrderAction, TriggerStatus, TradeType
from src.models.order_log import OrderLog
from src.storage.base import StorageBackend
from src.brokers import get_broker

logger = logging.getLogger('TriggerOrderManager')

# 券商實例快取設定
BROKER_CACHE_TTL_MINUTES = 30  # 快取存活時間 (分鐘)
BROKER_CACHE_MAX_SIZE = 50     # 快取最大數量


class TriggerOrderManager:
    """條件單管理器"""

    def __init__(self,
                 storage: StorageBackend,
                 user_manager,
                 telegram_token: str = ""):
        """
        初始化管理器

        Args:
            storage: 儲存後端
            user_manager: 用戶管理器
            telegram_token: Telegram Bot Token (用於發送通知)
        """
        self.storage = storage
        self.user_manager = user_manager
        self.telegram_token = telegram_token

        # 券商連線池 (復用 BotManager 的模式)
        # 格式: {broker_key: (broker_instance, last_access_time)}
        self._broker_instances: Dict[str, Tuple[object, datetime]] = {}
        self._broker_lock = threading.Lock()  # 券商實例存取鎖
        self._last_cleanup = datetime.now()

        # 執行中的條件單追蹤 (防止重複執行)
        self._executing_triggers: Set[str] = set()
        self._executing_lock = threading.Lock()

    # ========== CRUD 操作 ==========

    def create_trigger_order(self,
                             user_id: str,
                             symbol: str,
                             condition: str,
                             trigger_price: float,
                             order_action: str,
                             quantity: int,
                             order_type: str = "limit",
                             order_price: Optional[float] = None,
                             trade_type: str = "cash",
                             broker_name: str = "esun",
                             expires_at: Optional[datetime] = None,
                             note: str = "") -> TriggerOrder:
        """
        建立條件單

        Args:
            user_id: 用戶 ID (chat_id)
            symbol: 股票代號
            condition: 觸發條件 (">=", "<=", "==")
            trigger_price: 觸發價格
            order_action: 訂單方向 ("buy", "sell")
            quantity: 張數
            order_type: 訂單類型 ("market", "limit")
            order_price: 限價單價格
            trade_type: 交易類型 ("cash", "day_trade", "margin_buy", "short_sell")
            broker_name: 券商名稱
            expires_at: 過期時間
            note: 備註

        Returns:
            TriggerOrder: 建立的條件單
        """
        trigger = TriggerOrder(
            user_id=str(user_id),
            symbol=symbol.upper(),
            condition=TriggerCondition(condition),
            trigger_price=trigger_price,
            order_type=OrderType(order_type),
            order_action=OrderAction(order_action),
            trade_type=TradeType(trade_type),
            quantity=quantity,
            order_price=order_price,
            broker_name=broker_name,
            expires_at=expires_at,
            note=note
        )

        # 儲存
        self.storage.save_trigger_order(trigger)

        # 記錄日誌
        self._log_action(trigger, "created", True, "條件單已建立")

        logger.info(f"條件單已建立: {trigger.id} | {user_id} | {symbol} | "
                    f"{condition} {trigger_price}")
        return trigger

    def get_trigger_order(self, trigger_id: str) -> Optional[TriggerOrder]:
        """取得條件單"""
        return self.storage.get_trigger_order(trigger_id)

    def get_user_triggers(self,
                          user_id: str,
                          status: Optional[TriggerStatus] = None) -> List[TriggerOrder]:
        """
        取得用戶的條件單列表

        Args:
            user_id: 用戶 ID
            status: 篩選狀態 (可選)
        """
        return self.storage.get_user_triggers(str(user_id), status)

    def get_all_active_triggers(self) -> List[TriggerOrder]:
        """取得所有活躍的條件單"""
        triggers = self.storage.get_triggers_by_status(TriggerStatus.ACTIVE)

        # 過濾掉已過期的
        active_triggers = []
        for trigger in triggers:
            if trigger.is_expired():
                # 標記為過期
                trigger.status = TriggerStatus.EXPIRED
                trigger.updated_at = datetime.now()
                self.storage.save_trigger_order(trigger)
                self._log_action(trigger, "expired", True, "條件單已過期")
            else:
                active_triggers.append(trigger)

        return active_triggers

    def update_trigger_order(self,
                             trigger_id: str,
                             updates: dict,
                             user_id: Optional[str] = None) -> Optional[TriggerOrder]:
        """
        更新條件單

        Args:
            trigger_id: 條件單 ID
            updates: 更新內容
            user_id: 用戶 ID (用於權限驗證)
        """
        trigger = self.get_trigger_order(trigger_id)
        if not trigger:
            return None

        # 權限檢查
        if user_id and trigger.user_id != str(user_id):
            logger.warning(f"權限不足: {user_id} 嘗試更新 {trigger_id}")
            return None

        # 只能更新活躍的條件單
        if trigger.status != TriggerStatus.ACTIVE:
            logger.warning(f"無法更新非活躍的條件單: {trigger_id}")
            return None

        # 更新允許的欄位
        allowed_fields = [
            'trigger_price', 'order_price', 'quantity',
            'expires_at', 'note'
        ]

        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                setattr(trigger, field, updates[field])

        trigger.updated_at = datetime.now()
        self.storage.save_trigger_order(trigger)

        self._log_action(trigger, "updated", True, f"更新欄位: {list(updates.keys())}")

        logger.info(f"條件單已更新: {trigger_id}")
        return trigger

    def delete_trigger_order(self, trigger_id: str, user_id: str) -> bool:
        """
        刪除條件單

        Args:
            trigger_id: 條件單 ID
            user_id: 用戶 ID (用於權限驗證)
        """
        trigger = self.get_trigger_order(trigger_id)
        if not trigger:
            return False

        # 權限檢查
        if trigger.user_id != str(user_id):
            logger.warning(f"權限不足: {user_id} 嘗試刪除 {trigger_id}")
            return False

        success = self.storage.delete_trigger_order(trigger_id)
        if success:
            logger.info(f"條件單已刪除: {trigger_id}")

        return success

    def cancel_trigger_order(self, trigger_id: str, user_id: str) -> bool:
        """取消條件單 (軟刪除)"""
        trigger = self.get_trigger_order(trigger_id)
        if not trigger or trigger.user_id != str(user_id):
            return False

        if trigger.status != TriggerStatus.ACTIVE:
            return False

        trigger.status = TriggerStatus.CANCELLED
        trigger.updated_at = datetime.now()
        self.storage.save_trigger_order(trigger)

        self._log_action(trigger, "cancelled", True, "條件單已取消")

        logger.info(f"條件單已取消: {trigger_id}")
        return True

    # ========== 執行邏輯 ==========

    def execute_trigger(self, trigger: TriggerOrder, current_price: float) -> bool:
        """
        執行已觸發的條件單

        Args:
            trigger: 條件單
            current_price: 當前價格

        Returns:
            bool: 是否執行成功
        """
        # 防止重複執行 (使用原子操作檢查並標記)
        with self._executing_lock:
            if trigger.id in self._executing_triggers:
                logger.warning(f"條件單 {trigger.id} 已在執行中，跳過")
                return False
            # 重新檢查狀態 (可能在等待鎖期間被其他執行緒處理)
            fresh_trigger = self.storage.get_trigger_order(trigger.id)
            if fresh_trigger and fresh_trigger.status != TriggerStatus.ACTIVE:
                logger.warning(f"條件單 {trigger.id} 狀態已變更為 {fresh_trigger.status.value}，跳過")
                return False
            self._executing_triggers.add(trigger.id)

        try:
            user_id = trigger.user_id

            # 更新狀態為已觸發
            trigger.status = TriggerStatus.TRIGGERED
            trigger.triggered_at = datetime.now()
            self.storage.save_trigger_order(trigger)

            self._log_action(trigger, "triggered", True,
                             f"觸發價格: {current_price}",
                             current_price=current_price)

            # 取得券商實例
            broker = self._get_broker(user_id, trigger.broker_name)
            if not broker:
                raise Exception(f"無法連接券商 {trigger.broker_name}")

            # 決定下單價格
            if trigger.order_type == OrderType.MARKET:
                # 市價單使用漲停/跌停價
                order_price = 0  # 由券商處理
                use_market = True
            else:
                order_price = trigger.order_price or trigger.trigger_price
                use_market = False

            # 執行下單
            if trigger.order_action == OrderAction.BUY:
                if use_market and hasattr(broker, 'place_market_buy_order'):
                    result = broker.place_market_buy_order(
                        trigger.symbol, trigger.quantity
                    )
                else:
                    result = broker.place_buy_order(
                        trigger.symbol, order_price, trigger.quantity
                    )
            else:
                if use_market and hasattr(broker, 'place_market_sell_order'):
                    result = broker.place_market_sell_order(
                        trigger.symbol, trigger.quantity
                    )
                else:
                    result = broker.place_sell_order(
                        trigger.symbol, order_price, trigger.quantity
                    )

            # 更新條件單狀態
            if result.success:
                trigger.status = TriggerStatus.EXECUTED
                trigger.executed_at = datetime.now()
                trigger.executed_order_no = result.order_no
                trigger.execution_message = "執行成功"

                self._log_action(trigger, "executed", True,
                                 f"委託序號: {result.order_no}",
                                 order_no=result.order_no,
                                 current_price=current_price)

                # 發送通知
                self._send_notification(trigger, current_price, success=True)

                logger.info(f"條件單執行成功: {trigger.id} | 委託序號: {result.order_no}")
            else:
                trigger.status = TriggerStatus.FAILED
                trigger.execution_message = result.message

                self._log_action(trigger, "failed", False,
                                 result.message,
                                 current_price=current_price)

                self._send_notification(trigger, current_price,
                                        success=False, error=result.message)

                logger.error(f"條件單執行失敗: {trigger.id} | {result.message}")

            # 儲存更新
            self.storage.save_trigger_order(trigger)
            return result.success

        except Exception as e:
            trigger.status = TriggerStatus.FAILED
            trigger.execution_message = str(e)
            self.storage.save_trigger_order(trigger)

            self._log_action(trigger, "failed", False,
                             str(e),
                             current_price=current_price)

            self._send_notification(trigger, current_price,
                                    success=False, error=str(e))

            logger.error(f"條件單執行異常: {trigger.id} | {e}")
            return False

        finally:
            # 從執行中清單移除
            with self._executing_lock:
                self._executing_triggers.discard(trigger.id)

    def _get_broker(self, user_id: str, broker_name: str):
        """取得或建立券商實例 (含 TTL 快取管理，執行緒安全)"""
        broker_key = f"{user_id}_{broker_name}"

        # 定期清理過期快取
        self._cleanup_broker_cache()

        with self._broker_lock:
            if broker_key in self._broker_instances:
                broker, _ = self._broker_instances[broker_key]
                if broker.is_logged_in():
                    # 更新最後存取時間
                    self._broker_instances[broker_key] = (broker, datetime.now())
                    return broker
                else:
                    # 登出了，移除快取
                    del self._broker_instances[broker_key]

        # 取得券商設定 (在鎖外執行，避免長時間持有鎖)
        broker_config = self.user_manager.get_broker_config(user_id, broker_name)
        if not broker_config:
            logger.error(f"找不到券商設定: {user_id} / {broker_name}")
            return None

        try:
            broker = get_broker(broker_name, broker_config)
            if broker.login():
                with self._broker_lock:
                    # 雙重檢查，可能其他執行緒已建立
                    if broker_key in self._broker_instances:
                        # 使用已存在的，登出新建立的
                        existing_broker, _ = self._broker_instances[broker_key]
                        if existing_broker.is_logged_in():
                            try:
                                broker.logout()
                            except Exception:
                                pass
                            self._broker_instances[broker_key] = (existing_broker, datetime.now())
                            return existing_broker
                    self._broker_instances[broker_key] = (broker, datetime.now())
                return broker
            else:
                logger.error(f"券商登入失敗: {broker_name}")
        except Exception as e:
            logger.error(f"建立券商實例失敗: {e}")

        return None

    def _cleanup_broker_cache(self):
        """清理過期的券商實例快取 (執行緒安全)"""
        now = datetime.now()

        # 每 5 分鐘執行一次清理
        if (now - self._last_cleanup) < timedelta(minutes=5):
            return

        self._last_cleanup = now
        ttl = timedelta(minutes=BROKER_CACHE_TTL_MINUTES)

        with self._broker_lock:
            expired_keys = []
            brokers_to_logout = []

            for key, (broker, last_access) in self._broker_instances.items():
                if (now - last_access) > ttl:
                    expired_keys.append(key)
                    brokers_to_logout.append(broker)

            for key in expired_keys:
                del self._broker_instances[key]

            # 如果快取超過最大數量，移除最舊的
            if len(self._broker_instances) > BROKER_CACHE_MAX_SIZE:
                sorted_items = sorted(
                    self._broker_instances.items(),
                    key=lambda x: x[1][1]
                )
                to_remove = len(self._broker_instances) - BROKER_CACHE_MAX_SIZE
                for key, (broker, _) in sorted_items[:to_remove]:
                    brokers_to_logout.append(broker)
                    del self._broker_instances[key]

                if to_remove > 0:
                    logger.info(f"快取超過上限，已移除 {to_remove} 個券商實例")

        # 在鎖外登出券商，避免長時間持有鎖
        for broker in brokers_to_logout:
            try:
                if hasattr(broker, 'logout'):
                    broker.logout()
            except Exception as e:
                logger.warning(f"券商登出失敗: {e}")

        if expired_keys:
            logger.info(f"已清理 {len(expired_keys)} 個過期券商實例")

    def cleanup_all_brokers(self):
        """清理所有券商實例 (用於服務關閉時，執行緒安全)"""
        with self._broker_lock:
            brokers_to_logout = [broker for broker, _ in self._broker_instances.values()]
            self._broker_instances.clear()

        # 在鎖外登出券商
        for broker in brokers_to_logout:
            try:
                if hasattr(broker, 'logout'):
                    broker.logout()
            except Exception as e:
                logger.warning(f"券商登出失敗: {e}")

        logger.info("已清理所有券商實例")

    def _log_action(self,
                    trigger: TriggerOrder,
                    action: str,
                    success: bool,
                    message: str = "",
                    **kwargs):
        """記錄執行日誌"""
        log = OrderLog.create_log(
            trigger_order_id=trigger.id,
            user_id=trigger.user_id,
            action=action,
            success=success,
            message=message,
            trigger_price=trigger.trigger_price,
            **kwargs
        )
        self.storage.save_order_log(log)

    def _send_notification(self,
                           trigger: TriggerOrder,
                           current_price: float,
                           success: bool,
                           error: str = ""):
        """發送 Telegram 通知"""
        if not self.telegram_token:
            return

        try:
            from src.telegram.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier(
                bot_token=self.telegram_token,
                chat_id=trigger.user_id,
                enabled=True
            )

            if success:
                action = "買入" if trigger.order_action == OrderAction.BUY else "賣出"
                order_type = "市價" if trigger.order_type == OrderType.MARKET else "限價"

                message = f"""
<b>條件單已觸發執行</b>

股票: <code>{trigger.symbol}</code>
條件: {trigger.get_display_condition()}
觸發價格: {current_price}
動作: {order_type}{action} {trigger.quantity}張
委託序號: <code>{trigger.executed_order_no}</code>
時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            else:
                message = f"""
<b>條件單執行失敗</b>

股票: <code>{trigger.symbol}</code>
條件: {trigger.get_display_condition()}
觸發價格: {current_price}
錯誤: {error}
時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """

            notifier.send_message(message.strip())
        except Exception as e:
            logger.warning(f"發送通知失敗: {e}")

    # ========== API Key 管理 ==========

    def generate_api_key(self, user_id: str) -> str:
        """
        為用戶生成新的 API Key

        Args:
            user_id: 用戶 ID

        Returns:
            新的 API Key
        """
        api_key = f"sk-{secrets.token_urlsafe(32)}"
        self.storage.save_user_api_key(str(user_id), api_key)
        logger.info(f"已為用戶 {user_id} 生成新的 API Key")
        return api_key

    def get_user_by_api_key(self, api_key: str) -> Optional[str]:
        """透過 API Key 取得用戶 ID"""
        return self.storage.get_user_by_api_key(api_key)

    # ========== 統計資訊 ==========

    def get_user_stats(self, user_id: str) -> dict:
        """取得用戶統計資訊"""
        triggers = self.get_user_triggers(str(user_id))

        stats = {
            'total': len(triggers),
            'active': 0,
            'triggered': 0,
            'executed': 0,
            'failed': 0,
            'cancelled': 0
        }

        for trigger in triggers:
            if trigger.status == TriggerStatus.ACTIVE:
                stats['active'] += 1
            elif trigger.status == TriggerStatus.TRIGGERED:
                stats['triggered'] += 1
            elif trigger.status == TriggerStatus.EXECUTED:
                stats['executed'] += 1
            elif trigger.status == TriggerStatus.FAILED:
                stats['failed'] += 1
            elif trigger.status == TriggerStatus.CANCELLED:
                stats['cancelled'] += 1

        return stats

    def cleanup_old_triggers(self, days: int = 30) -> int:
        """
        清理舊的非活躍條件單

        Args:
            days: 保留天數

        Returns:
            清理的數量
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0

        for status in [TriggerStatus.EXECUTED, TriggerStatus.FAILED,
                       TriggerStatus.CANCELLED, TriggerStatus.EXPIRED]:
            triggers = self.storage.get_triggers_by_status(status)
            for trigger in triggers:
                if trigger.updated_at < cutoff:
                    self.storage.delete_trigger_order(trigger.id)
                    cleaned += 1

        if cleaned > 0:
            logger.info(f"已清理 {cleaned} 個舊條件單")

        return cleaned
