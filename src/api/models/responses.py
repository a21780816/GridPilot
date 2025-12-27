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
    close: Optional[float] = Field(None, description="收盤價")
    yesterday: Optional[float] = Field(None, description="昨收價")
    volume: Optional[int] = Field(None, description="成交量 (張)")
    amount: Optional[float] = Field(None, description="成交金額 (元)")
    bid_price: Optional[float] = Field(None, description="買進價 (最佳買價)")
    ask_price: Optional[float] = Field(None, description="賣出價 (最佳賣價)")
    limit_up: Optional[float] = Field(None, description="漲停價")
    limit_down: Optional[float] = Field(None, description="跌停價")
    amplitude: Optional[float] = Field(None, description="振幅 %")
    timestamp: Optional[str] = Field(None, description="報價時間")
    market: Optional[str] = Field(None, description="市場 (tse/otc)")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "2330",
                "name": "台積電",
                "price": 600.0,
                "change": 5.0,
                "change_percent": 0.84,
                "open": 598.0,
                "high": 605.0,
                "low": 597.0,
                "close": 600.0,
                "yesterday": 595.0,
                "volume": 25000,
                "amount": 15000000000,
                "bid_price": 599.0,
                "ask_price": 600.0,
                "limit_up": 654.0,
                "limit_down": 536.0,
                "amplitude": 1.34,
                "timestamp": "13:30:00",
                "market": "tse"
            }
        }


class StockFundamentalResponse(BaseModel):
    """股票基本面響應"""
    symbol: str = Field(..., description="股票代號")
    name: Optional[str] = Field(None, description="股票名稱")
    pe_ratio: Optional[float] = Field(None, description="本益比")
    pb_ratio: Optional[float] = Field(None, description="股價淨值比")
    dividend_yield: Optional[float] = Field(None, description="殖利率 %")
    eps: Optional[float] = Field(None, description="每股盈餘")
    market_cap: Optional[float] = Field(None, description="市值 (億)")
    shares_outstanding: Optional[int] = Field(None, description="流通股數")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "2330",
                "name": "台積電",
                "pe_ratio": 18.5,
                "pb_ratio": 4.2,
                "dividend_yield": 2.5,
                "eps": 32.5,
                "market_cap": 155000,
                "shares_outstanding": 25930000000
            }
        }


class InstitutionalInvestorResponse(BaseModel):
    """法人買賣超響應"""
    symbol: str = Field(..., description="股票代號")
    date: Optional[str] = Field(None, description="資料日期")
    foreign_buy: Optional[int] = Field(None, description="外資買 (張)")
    foreign_sell: Optional[int] = Field(None, description="外資賣 (張)")
    foreign_net: Optional[int] = Field(None, description="外資買賣超 (張)")
    investment_trust_buy: Optional[int] = Field(None, description="投信買 (張)")
    investment_trust_sell: Optional[int] = Field(None, description="投信賣 (張)")
    investment_trust_net: Optional[int] = Field(None, description="投信買賣超 (張)")
    dealer_buy: Optional[int] = Field(None, description="自營商買 (張)")
    dealer_sell: Optional[int] = Field(None, description="自營商賣 (張)")
    dealer_net: Optional[int] = Field(None, description="自營商買賣超 (張)")
    total_net: Optional[int] = Field(None, description="三大法人合計買賣超")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "2330",
                "date": "20250127",
                "foreign_buy": 15000,
                "foreign_sell": 10000,
                "foreign_net": 5000,
                "investment_trust_buy": 2000,
                "investment_trust_sell": 1000,
                "investment_trust_net": 1000,
                "dealer_buy": 500,
                "dealer_sell": 300,
                "dealer_net": 200,
                "total_net": 6200
            }
        }


class StockDetailResponse(BaseModel):
    """股票完整資訊響應"""
    quote: StockQuoteResponse = Field(..., description="報價資訊")
    fundamental: Optional[StockFundamentalResponse] = Field(None, description="基本面資訊")
    institutional: Optional[InstitutionalInvestorResponse] = Field(None, description="法人買賣超")


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


# ==================== Portfolio 響應模型 ====================

class PositionResponse(BaseModel):
    """持倉響應"""
    symbol: str = Field(..., description="股票代號")
    symbol_name: str = Field("", description="股票名稱")
    quantity: int = Field(..., description="持有張數")
    avg_price: float = Field(..., description="平均成本")
    current_price: float = Field(0, description="現價")
    unrealized_pnl: float = Field(0, description="未實現損益")
    unrealized_pnl_percent: float = Field(0, description="未實現損益率 %")
    market_value: float = Field(0, description="市值")
    cost_value: float = Field(0, description="成本金額")
    today_pnl: float = Field(0, description="今日損益")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "2330",
                "symbol_name": "台積電",
                "quantity": 2,
                "avg_price": 580.5,
                "current_price": 600.0,
                "unrealized_pnl": 39000,
                "unrealized_pnl_percent": 3.36,
                "market_value": 1200000,
                "cost_value": 1161000,
                "today_pnl": 5000
            }
        }


class PositionListResponse(BaseModel):
    """持倉列表響應"""
    total: int = Field(..., description="持倉數量")
    total_market_value: float = Field(0, description="總市值")
    total_cost_value: float = Field(0, description="總成本")
    total_unrealized_pnl: float = Field(0, description="總未實現損益")
    total_unrealized_pnl_percent: float = Field(0, description="總未實現損益率 %")
    items: List[PositionResponse] = Field(..., description="持倉列表")


class AccountBalanceResponse(BaseModel):
    """帳戶餘額響應"""
    available_balance: float = Field(0, description="可用餘額")
    total_balance: float = Field(0, description="帳戶總額")
    settled_balance: float = Field(0, description="已交割餘額")
    unsettled_amount: float = Field(0, description="未交割金額")
    margin_available: float = Field(0, description="融資可用額度")
    short_available: float = Field(0, description="融券可用額度")
    currency: str = Field("TWD", description="幣別")

    class Config:
        json_schema_extra = {
            "example": {
                "available_balance": 500000.0,
                "total_balance": 1500000.0,
                "settled_balance": 500000.0,
                "unsettled_amount": 100000.0,
                "margin_available": 0,
                "short_available": 0,
                "currency": "TWD"
            }
        }


class OrderInfoResponse(BaseModel):
    """訂單資訊響應"""
    order_no: str = Field(..., description="委託書號")
    symbol: str = Field(..., description="股票代號")
    symbol_name: str = Field("", description="股票名稱")
    side: str = Field(..., description="買賣方向 (buy/sell)")
    price: float = Field(0, description="委託價")
    quantity: int = Field(0, description="委託張數")
    filled_qty: int = Field(0, description="成交張數")
    filled_price: float = Field(0, description="成交均價")
    status: str = Field(..., description="狀態 (pending/partial/filled/cancelled/failed)")
    order_time: Optional[datetime] = Field(None, description="委託時間")
    trade_type: str = Field("cash", description="交易類型")

    class Config:
        json_schema_extra = {
            "example": {
                "order_no": "A0001",
                "symbol": "2330",
                "symbol_name": "台積電",
                "side": "buy",
                "price": 600.0,
                "quantity": 1,
                "filled_qty": 1,
                "filled_price": 599.5,
                "status": "filled",
                "order_time": "2025-01-15T09:00:00",
                "trade_type": "cash"
            }
        }


class OrderListResponse(BaseModel):
    """訂單列表響應"""
    total: int = Field(..., description="訂單數量")
    items: List[OrderInfoResponse] = Field(..., description="訂單列表")


class TransactionResponse(BaseModel):
    """成交紀錄響應"""
    trade_no: str = Field("", description="成交序號")
    order_no: str = Field("", description="委託書號")
    symbol: str = Field(..., description="股票代號")
    symbol_name: str = Field("", description="股票名稱")
    side: str = Field(..., description="買賣方向 (buy/sell)")
    price: float = Field(0, description="成交價")
    quantity: int = Field(0, description="成交張數")
    amount: float = Field(0, description="成交金額")
    fee: float = Field(0, description="手續費")
    tax: float = Field(0, description="交易稅")
    net_amount: float = Field(0, description="淨收付金額")
    trade_time: Optional[datetime] = Field(None, description="成交時間")
    trade_type: str = Field("cash", description="交易類型")

    class Config:
        json_schema_extra = {
            "example": {
                "trade_no": "T0001",
                "order_no": "A0001",
                "symbol": "2330",
                "symbol_name": "台積電",
                "side": "buy",
                "price": 599.5,
                "quantity": 1,
                "amount": 599500,
                "fee": 855,
                "tax": 0,
                "net_amount": 600355,
                "trade_time": "2025-01-15T09:05:00",
                "trade_type": "cash"
            }
        }


class TransactionListResponse(BaseModel):
    """成交紀錄列表響應"""
    total: int = Field(..., description="成交筆數")
    total_amount: float = Field(0, description="總成交金額")
    total_fee: float = Field(0, description="總手續費")
    total_tax: float = Field(0, description="總交易稅")
    items: List[TransactionResponse] = Field(..., description="成交紀錄列表")


class SettlementResponse(BaseModel):
    """交割資訊響應"""
    date: str = Field(..., description="交割日期")
    amount: float = Field(0, description="交割金額")
    status: str = Field("", description="交割狀態")


class SettlementListResponse(BaseModel):
    """交割資訊列表響應"""
    total: int = Field(..., description="交割筆數")
    items: List[SettlementResponse] = Field(..., description="交割資訊列表")


class PortfolioSummaryResponse(BaseModel):
    """投資組合摘要響應"""
    total_market_value: float = Field(0, description="總市值")
    total_cost_value: float = Field(0, description="總成本")
    total_unrealized_pnl: float = Field(0, description="總未實現損益")
    total_unrealized_pnl_percent: float = Field(0, description="總未實現損益率 %")
    available_balance: float = Field(0, description="可用餘額")
    total_assets: float = Field(0, description="總資產 (市值 + 可用餘額)")
    position_count: int = Field(0, description="持股數量")

    class Config:
        json_schema_extra = {
            "example": {
                "total_market_value": 2500000,
                "total_cost_value": 2400000,
                "total_unrealized_pnl": 100000,
                "total_unrealized_pnl_percent": 4.17,
                "available_balance": 500000,
                "total_assets": 3000000,
                "position_count": 5
            }
        }
