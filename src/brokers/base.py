"""
券商抽象基類
定義所有券商需要實作的介面
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderResult:
    """下單結果"""
    success: bool
    order_no: Optional[str] = None
    message: str = ""


@dataclass
class Position:
    """持倉資訊"""
    symbol: str
    symbol_name: str = ""  # 股票名稱
    quantity: int = 0  # 張數
    avg_price: float = 0  # 平均成本
    current_price: float = 0  # 現價
    unrealized_pnl: float = 0  # 未實現損益
    unrealized_pnl_percent: float = 0  # 未實現損益率
    market_value: float = 0  # 市值
    cost_value: float = 0  # 成本金額
    today_pnl: float = 0  # 今日損益


@dataclass
class OrderInfo:
    """訂單資訊"""
    order_no: str
    symbol: str
    symbol_name: str = ""  # 股票名稱
    side: str = ""  # 'buy' or 'sell'
    price: float = 0  # 委託價
    quantity: int = 0  # 委託張數
    filled_qty: int = 0  # 成交張數
    filled_price: float = 0  # 成交均價
    status: str = ""  # 'pending', 'partial', 'filled', 'cancelled', 'failed'
    order_time: Optional[datetime] = None  # 委託時間
    trade_type: str = "cash"  # 交易類型


@dataclass
class AccountBalance:
    """帳戶餘額資訊"""
    available_balance: float = 0  # 可用餘額
    total_balance: float = 0  # 帳戶總額
    settled_balance: float = 0  # 已交割餘額
    unsettled_amount: float = 0  # 未交割金額
    margin_available: float = 0  # 融資可用額度
    short_available: float = 0  # 融券可用額度
    maintenance_margin: float = 0  # 維持保證金
    currency: str = "TWD"  # 幣別


@dataclass
class Transaction:
    """成交紀錄"""
    trade_no: str = ""  # 成交序號
    order_no: str = ""  # 委託書號
    symbol: str = ""
    symbol_name: str = ""
    side: str = ""  # 'buy' or 'sell'
    price: float = 0  # 成交價
    quantity: int = 0  # 成交張數
    amount: float = 0  # 成交金額
    fee: float = 0  # 手續費
    tax: float = 0  # 交易稅
    net_amount: float = 0  # 淨收付金額
    trade_time: Optional[datetime] = None  # 成交時間
    trade_type: str = "cash"  # 交易類型


@dataclass
class Settlement:
    """交割資訊"""
    date: str = ""  # 交割日期
    amount: float = 0  # 交割金額
    status: str = ""  # 交割狀態


class BaseBroker(ABC):
    """券商抽象基類"""

    def __init__(self, config: Dict):
        """
        初始化券商

        Args:
            config: 券商設定，包含 API 憑證等
        """
        self.config = config
        self._logged_in = False

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """券商名稱"""
        pass

    @abstractmethod
    def login(self) -> bool:
        """
        登入券商 API

        Returns:
            bool: 是否登入成功
        """
        pass

    @abstractmethod
    def logout(self):
        """登出"""
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        取得股票當前價格

        Args:
            symbol: 股票代號

        Returns:
            float: 當前價格，失敗返回 None
        """
        pass

    @abstractmethod
    def place_buy_order(self, symbol: str, price: float, quantity: int) -> OrderResult:
        """
        下買單

        Args:
            symbol: 股票代號
            price: 買入價格
            quantity: 買入數量（張）

        Returns:
            OrderResult: 下單結果
        """
        pass

    @abstractmethod
    def place_sell_order(self, symbol: str, price: float, quantity: int) -> OrderResult:
        """
        下賣單

        Args:
            symbol: 股票代號
            price: 賣出價格
            quantity: 賣出數量（張）

        Returns:
            OrderResult: 下單結果
        """
        pass

    def place_market_buy_order(self, symbol: str, quantity: int) -> OrderResult:
        """
        下市價買單

        Args:
            symbol: 股票代號
            quantity: 買入數量（張）

        Returns:
            OrderResult: 下單結果

        Note:
            子類別必須覆寫此方法，使用券商的市價單 API 或漲停價模擬
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作市價買單功能，請覆寫 place_market_buy_order 方法"
        )

    def place_market_sell_order(self, symbol: str, quantity: int) -> OrderResult:
        """
        下市價賣單

        Args:
            symbol: 股票代號
            quantity: 賣出數量（張）

        Returns:
            OrderResult: 下單結果

        Note:
            子類別必須覆寫此方法，使用券商的市價單 API 或跌停價模擬
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作市價賣單功能，請覆寫 place_market_sell_order 方法"
        )

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        取得持倉

        Args:
            symbol: 股票代號

        Returns:
            Position: 持倉資訊，無持倉返回 None
        """
        pass

    @abstractmethod
    def get_order_status(self, order_no: str) -> Optional[OrderInfo]:
        """
        查詢訂單狀態

        Args:
            order_no: 訂單編號

        Returns:
            OrderInfo: 訂單資訊
        """
        pass

    @abstractmethod
    def get_orders(self) -> List[OrderInfo]:
        """
        取得所有訂單

        Returns:
            List[OrderInfo]: 訂單列表
        """
        pass

    def get_all_positions(self) -> List[Position]:
        """
        取得所有持倉

        Returns:
            List[Position]: 持倉列表
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作取得所有持倉功能"
        )

    def get_balance(self) -> Optional[AccountBalance]:
        """
        取得帳戶餘額

        Returns:
            AccountBalance: 帳戶餘額資訊
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作取得帳戶餘額功能"
        )

    def get_transactions(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Transaction]:
        """
        取得成交紀錄

        Args:
            start_date: 開始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)

        Returns:
            List[Transaction]: 成交紀錄列表
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作取得成交紀錄功能"
        )

    def get_settlements(self) -> List[Settlement]:
        """
        取得交割資訊

        Returns:
            List[Settlement]: 交割資訊列表
        """
        raise NotImplementedError(
            f"{self.broker_name} 尚未實作取得交割資訊功能"
        )

    def is_logged_in(self) -> bool:
        """是否已登入"""
        return self._logged_in

    @staticmethod
    @abstractmethod
    def get_required_config_fields() -> List[Dict]:
        """
        取得需要的設定欄位

        Returns:
            List[Dict]: 設定欄位列表
                - name: 欄位名稱
                - description: 說明
                - type: 類型 (text, password, file)
                - required: 是否必填
        """
        pass

    @staticmethod
    @abstractmethod
    def validate_config(config: Dict) -> tuple:
        """
        驗證設定是否完整

        Args:
            config: 設定

        Returns:
            tuple: (is_valid, error_message)
        """
        pass
