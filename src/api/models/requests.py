"""
API 請求模型
"""

from typing import Optional
from pydantic import BaseModel, Field

from src.models.enums import TriggerCondition, OrderType, OrderAction, TradeType


class CreateTriggerOrderRequest(BaseModel):
    """建立條件單請求"""
    symbol: str = Field(..., description="股票代號", min_length=1, max_length=10)
    condition: TriggerCondition = Field(..., description="觸發條件 (>=, <=, ==)")
    trigger_price: float = Field(..., description="觸發價格", gt=0)
    order_type: OrderType = Field(..., description="訂單類型 (market, limit)")
    order_action: OrderAction = Field(..., description="交易方向 (buy, sell)")
    trade_type: TradeType = Field(
        TradeType.CASH,
        description="交易類型 (cash=現股, day_trade=現沖, margin_buy=融資, short_sell=融券)"
    )
    quantity: int = Field(..., description="交易張數", gt=0, le=999)
    order_price: Optional[float] = Field(
        None,
        description="限價單委託價格 (僅限價單需要)",
        gt=0
    )
    broker_name: Optional[str] = Field(
        None,
        description="券商名稱 (預設使用第一個設定的券商)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "2330",
                "condition": ">=",
                "trigger_price": 600.0,
                "order_type": "market",
                "order_action": "buy",
                "trade_type": "cash",
                "quantity": 1,
                "broker_name": "esun"
            }
        }


class UpdateTriggerOrderRequest(BaseModel):
    """更新條件單請求"""
    trigger_price: Optional[float] = Field(None, description="觸發價格", gt=0)
    order_price: Optional[float] = Field(None, description="限價單委託價格", gt=0)
    quantity: Optional[int] = Field(None, description="交易張數", gt=0, le=999)

    class Config:
        json_schema_extra = {
            "example": {
                "trigger_price": 610.0,
                "quantity": 2
            }
        }
