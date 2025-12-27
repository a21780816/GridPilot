"""
條件單資料模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from .enums import TriggerCondition, OrderType, OrderAction, TriggerStatus, TradeType


@dataclass
class TriggerOrder:
    """條件單資料模型"""

    # 識別資訊
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""               # Telegram chat_id

    # 股票資訊
    symbol: str = ""                # 股票代號
    symbol_name: str = ""           # 股票名稱 (選填)

    # 觸發條件
    condition: TriggerCondition = TriggerCondition.GREATER_EQUAL
    trigger_price: float = 0.0      # 觸發價格

    # 訂單設定
    order_type: OrderType = OrderType.LIMIT
    order_action: OrderAction = OrderAction.BUY
    order_price: Optional[float] = None     # 限價單價格 (市價單為 None)
    trade_type: TradeType = TradeType.CASH  # 交易類型 (現股/現沖/融資/融券)
    quantity: int = 1                        # 張數

    # 券商設定
    broker_name: str = "esun"

    # 狀態追蹤
    status: TriggerStatus = TriggerStatus.ACTIVE

    # 時間戳記
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    triggered_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None   # 過期時間 (選填)

    # 執行結果
    executed_order_no: Optional[str] = None
    execution_message: str = ""

    # 備註
    note: str = ""

    def is_condition_met(self, current_price: float, tolerance: float = 0.01) -> bool:
        """
        檢查是否滿足觸發條件

        Args:
            current_price: 當前價格
            tolerance: 比較容差值 (用於浮點數精度問題)

        Returns:
            bool: 是否滿足條件
        """
        # 使用容差值處理浮點數精度問題
        # 例如: 100.0 >= 100.0 可能因浮點精度變成 99.9999999 < 100.0
        if self.condition == TriggerCondition.GREATER_EQUAL:
            # current_price >= trigger_price - tolerance
            return current_price >= (self.trigger_price - tolerance)
        elif self.condition == TriggerCondition.LESS_EQUAL:
            # current_price <= trigger_price + tolerance
            return current_price <= (self.trigger_price + tolerance)
        elif self.condition == TriggerCondition.EQUAL:
            return abs(current_price - self.trigger_price) <= tolerance
        return False

    def is_expired(self) -> bool:
        """檢查是否已過期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def can_execute(self) -> bool:
        """檢查是否可以執行"""
        return (
            self.status == TriggerStatus.ACTIVE and
            not self.is_expired()
        )

    def get_display_condition(self) -> str:
        """取得顯示用的條件字串"""
        return f"價格 {self.condition.value} {self.trigger_price}"

    def get_display_action(self) -> str:
        """取得顯示用的動作字串"""
        action = "買入" if self.order_action == OrderAction.BUY else "賣出"
        order_type = "市價" if self.order_type == OrderType.MARKET else "限價"
        trade_type_map = {
            TradeType.CASH: "現股",
            TradeType.DAY_TRADE: "現沖",
            TradeType.MARGIN_BUY: "融資",
            TradeType.SHORT_SELL: "融券",
        }
        trade_type = trade_type_map.get(self.trade_type, "現股")

        if self.order_type == OrderType.LIMIT and self.order_price:
            return f"{trade_type} {order_type}{action} {self.quantity}張 @ {self.order_price}"
        return f"{trade_type} {order_type}{action} {self.quantity}張"

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'symbol_name': self.symbol_name,
            'condition': self.condition.value,
            'trigger_price': self.trigger_price,
            'order_type': self.order_type.value,
            'order_action': self.order_action.value,
            'order_price': self.order_price,
            'trade_type': self.trade_type.value,
            'quantity': self.quantity,
            'broker_name': self.broker_name,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'executed_order_no': self.executed_order_no,
            'execution_message': self.execution_message,
            'note': self.note
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TriggerOrder':
        """從字典建立"""
        import logging
        logger = logging.getLogger('TriggerOrder')

        def parse_datetime(value):
            """安全解析日期時間，處理無效格式"""
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError) as e:
                logger.warning(f"日期解析失敗 '{value}': {e}")
                return None

        return cls(
            id=data.get('id', str(uuid.uuid4())),
            user_id=data.get('user_id', ''),
            symbol=data.get('symbol', ''),
            symbol_name=data.get('symbol_name', ''),
            condition=TriggerCondition(data.get('condition', '>=')),
            trigger_price=float(data.get('trigger_price', 0)),
            order_type=OrderType(data.get('order_type', 'limit')),
            order_action=OrderAction(data.get('order_action', 'buy')),
            order_price=data.get('order_price'),
            trade_type=TradeType(data.get('trade_type', 'cash')),
            quantity=int(data.get('quantity', 1)),
            broker_name=data.get('broker_name', 'esun'),
            status=TriggerStatus(data.get('status', 'active')),
            created_at=parse_datetime(data.get('created_at')) or datetime.now(),
            updated_at=parse_datetime(data.get('updated_at')) or datetime.now(),
            triggered_at=parse_datetime(data.get('triggered_at')),
            executed_at=parse_datetime(data.get('executed_at')),
            expires_at=parse_datetime(data.get('expires_at')),
            executed_order_no=data.get('executed_order_no'),
            execution_message=data.get('execution_message', ''),
            note=data.get('note', '')
        )

    def __repr__(self) -> str:
        return (
            f"TriggerOrder(id={self.id[:8]}..., symbol={self.symbol}, "
            f"condition={self.condition.value} {self.trigger_price}, "
            f"status={self.status.value})"
        )
