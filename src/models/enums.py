"""
列舉類型定義
"""

from enum import Enum


class TriggerCondition(str, Enum):
    """觸發條件類型"""
    GREATER_EQUAL = ">="    # 價格 >= 目標價
    LESS_EQUAL = "<="       # 價格 <= 目標價
    EQUAL = "=="            # 價格 == 目標價 (使用容差比較)


class OrderType(str, Enum):
    """訂單類型"""
    MARKET = "market"       # 市價單
    LIMIT = "limit"         # 限價單


class OrderAction(str, Enum):
    """訂單方向"""
    BUY = "buy"
    SELL = "sell"


class TriggerStatus(str, Enum):
    """條件單狀態"""
    ACTIVE = "active"           # 監控中
    TRIGGERED = "triggered"     # 已觸發
    EXECUTED = "executed"       # 已執行
    FAILED = "failed"           # 執行失敗
    CANCELLED = "cancelled"     # 已取消
    EXPIRED = "expired"         # 已過期


class TradeType(str, Enum):
    """交易類型"""
    CASH = "cash"               # 現股
    DAY_TRADE = "day_trade"     # 現沖 (當沖)
    MARGIN_BUY = "margin_buy"   # 融資買進
    SHORT_SELL = "short_sell"   # 融券賣出
