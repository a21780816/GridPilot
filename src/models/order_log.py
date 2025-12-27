"""
訂單執行紀錄模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


@dataclass
class OrderLog:
    """訂單執行紀錄"""

    # 識別資訊
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger_order_id: str = ""
    user_id: str = ""

    # 執行資訊
    action: str = ""                    # "created", "triggered", "executed", "failed", "cancelled"
    order_no: Optional[str] = None      # 券商委託序號

    # 價格資訊
    trigger_price: float = 0.0          # 設定的觸發價格
    current_price: Optional[float] = None   # 觸發時的市場價格
    execution_price: Optional[float] = None  # 實際執行價格

    # 狀態
    success: bool = False
    message: str = ""

    # 額外資料
    extra_data: Optional[Dict[str, Any]] = None

    # 時間
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            'id': self.id,
            'trigger_order_id': self.trigger_order_id,
            'user_id': self.user_id,
            'action': self.action,
            'order_no': self.order_no,
            'trigger_price': self.trigger_price,
            'current_price': self.current_price,
            'execution_price': self.execution_price,
            'success': self.success,
            'message': self.message,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'OrderLog':
        """從字典建立"""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data.get('id', str(uuid.uuid4())),
            trigger_order_id=data.get('trigger_order_id', ''),
            user_id=data.get('user_id', ''),
            action=data.get('action', ''),
            order_no=data.get('order_no'),
            trigger_price=float(data.get('trigger_price', 0)),
            current_price=data.get('current_price'),
            execution_price=data.get('execution_price'),
            success=data.get('success', False),
            message=data.get('message', ''),
            extra_data=data.get('extra_data'),
            created_at=created_at
        )

    @classmethod
    def create_log(cls,
                   trigger_order_id: str,
                   user_id: str,
                   action: str,
                   success: bool = True,
                   message: str = "",
                   **kwargs) -> 'OrderLog':
        """建立日誌的便捷方法"""
        return cls(
            trigger_order_id=trigger_order_id,
            user_id=user_id,
            action=action,
            success=success,
            message=message,
            **kwargs
        )

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return (
            f"OrderLog(trigger={self.trigger_order_id[:8]}..., "
            f"action={self.action}, status={status})"
        )
