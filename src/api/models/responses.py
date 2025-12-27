"""
API 響應模型
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TriggerOrderResponse(BaseModel):
    """條件單響應"""
    id: str = Field(..., description="條件單 ID")
    symbol: str = Field(..., description="股票代號")
    condition: str = Field(..., description="觸發條件")
    trigger_price: float = Field(..., description="觸發價格")
    order_type: str = Field(..., description="訂單類型")
    order_action: str = Field(..., description="交易方向")
    trade_type: str = Field(..., description="交易類型 (cash, day_trade, margin_buy, short_sell)")
    order_price: Optional[float] = Field(None, description="限價單價格")
    quantity: int = Field(..., description="交易張數")
    broker_name: str = Field(..., description="券商名稱")
    status: str = Field(..., description="狀態")
    created_at: datetime = Field(..., description="建立時間")
    triggered_at: Optional[datetime] = Field(None, description="觸發時間")
    executed_at: Optional[datetime] = Field(None, description="執行時間")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc12345-1234-5678-90ab-cdef01234567",
                "symbol": "2330",
                "condition": ">=",
                "trigger_price": 600.0,
                "order_type": "market",
                "order_action": "buy",
                "trade_type": "cash",
                "order_price": None,
                "quantity": 1,
                "broker_name": "esun",
                "status": "active",
                "created_at": "2025-01-15T10:30:00",
                "triggered_at": None,
                "executed_at": None
            }
        }


class TriggerOrderListResponse(BaseModel):
    """條件單列表響應"""
    total: int = Field(..., description="總數")
    items: List[TriggerOrderResponse] = Field(..., description="條件單列表")


class StockQuoteResponse(BaseModel):
    """股票報價響應"""
    symbol: str = Field(..., description="股票代號")
    name: Optional[str] = Field(None, description="股票名稱")
    price: float = Field(..., description="當前價格")
    change: Optional[float] = Field(None, description="漲跌")
    change_percent: Optional[float] = Field(None, description="漲跌幅 %")
    open: Optional[float] = Field(None, description="開盤價")
    high: Optional[float] = Field(None, description="最高價")
    low: Optional[float] = Field(None, description="最低價")
    volume: Optional[int] = Field(None, description="成交量")
    timestamp: Optional[datetime] = Field(None, description="報價時間")


class ErrorResponse(BaseModel):
    """錯誤響應"""
    error: str = Field(..., description="錯誤代碼")
    message: str = Field(..., description="錯誤訊息")
    detail: Optional[str] = Field(None, description="詳細資訊")


class SuccessResponse(BaseModel):
    """成功響應"""
    success: bool = Field(True, description="是否成功")
    message: str = Field(..., description="訊息")


class ApiKeyResponse(BaseModel):
    """API Key 響應"""
    api_key: str = Field(..., description="API Key (完整或部分遮罩)")
    created_at: Optional[datetime] = Field(None, description="建立時間")
