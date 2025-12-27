"""
玉山富果券商實作
"""

import logging
from typing import Dict, List, Optional
from configparser import ConfigParser
from pathlib import Path

from .base import BaseBroker, OrderResult, Position, OrderInfo

logger = logging.getLogger('EsunBroker')


class EsunBroker(BaseBroker):
    """玉山富果券商"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.trade_sdk = None
        self.market_sdk = None
        self.stock = None

    @property
    def broker_name(self) -> str:
        return "玉山富果"

    def login(self) -> bool:
        """登入玉山富果 API"""
        try:
            from esun_trade.sdk import SDK
            from esun_marketdata import EsunMarketdata

            # 建立 ConfigParser
            ini_config = ConfigParser()

            # 從 config dict 建立 ini 設定
            ini_config['User'] = {
                'Account': self.config.get('account', ''),
                'Password': self.config.get('password', ''),
            }
            ini_config['Cert'] = {
                'Path': self.config.get('cert_path', ''),
                'Password': self.config.get('cert_password', ''),
            }
            ini_config['Api'] = {
                'Key': self.config.get('api_key', ''),
                'Secret': self.config.get('api_secret', ''),
            }

            # 如果有提供 config_file，直接使用
            if 'config_file' in self.config:
                ini_config.read(self.config['config_file'])

            # 初始化交易 SDK
            self.trade_sdk = SDK(ini_config)
            self.trade_sdk.login()
            logger.info("玉山交易 SDK 登入成功")

            # 初始化市場數據 SDK
            self.market_sdk = EsunMarketdata(ini_config)
            self.market_sdk.login()
            self.stock = self.market_sdk.rest_client.stock
            logger.info("玉山市場數據 API 初始化成功")

            self._logged_in = True
            return True

        except Exception as e:
            logger.error(f"玉山 API 登入失敗: {e}")
            self._logged_in = False
            return False

    def logout(self):
        """登出"""
        self._logged_in = False
        self.trade_sdk = None
        self.market_sdk = None
        self.stock = None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """取得當前股價"""
        if not self._logged_in:
            return None

        try:
            quote = self.stock.intraday.quote(symbol=symbol)
            return quote.get('closePrice')
        except Exception as e:
            logger.error(f"取得股價失敗 {symbol}: {e}")
            return None

    def place_buy_order(self, symbol: str, price: float, quantity: int) -> OrderResult:
        """下買單"""
        if not self._logged_in:
            return OrderResult(success=False, message="未登入")

        try:
            from esun_trade.order import OrderObject
            from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action

            order = OrderObject(
                stock_no=symbol,
                buy_sell=Action.Buy,
                quantity=quantity,
                price=price,
                price_flag=PriceFlag.Limit,
                ap_code=APCode.Common,
                bs_flag=BSFlag.ROD,
                trade=Trade.Cash
            )

            result = self.trade_sdk.place_order(order)
            order_no = result.get('ord_no')

            if order_no:
                logger.info(f"買單已送出: {symbol} @ {price}, 數量: {quantity} 張")
                return OrderResult(success=True, order_no=order_no)
            else:
                return OrderResult(success=False, message=str(result))

        except Exception as e:
            logger.error(f"下買單失敗: {e}")
            return OrderResult(success=False, message=str(e))

    def place_sell_order(self, symbol: str, price: float, quantity: int) -> OrderResult:
        """下賣單"""
        if not self._logged_in:
            return OrderResult(success=False, message="未登入")

        try:
            from esun_trade.order import OrderObject
            from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action

            order = OrderObject(
                stock_no=symbol,
                buy_sell=Action.Sell,
                quantity=quantity,
                price=price,
                price_flag=PriceFlag.Limit,
                ap_code=APCode.Common,
                bs_flag=BSFlag.ROD,
                trade=Trade.Cash
            )

            result = self.trade_sdk.place_order(order)
            order_no = result.get('ord_no')

            if order_no:
                logger.info(f"賣單已送出: {symbol} @ {price}, 數量: {quantity} 張")
                return OrderResult(success=True, order_no=order_no)
            else:
                return OrderResult(success=False, message=str(result))

        except Exception as e:
            logger.error(f"下賣單失敗: {e}")
            return OrderResult(success=False, message=str(e))

    def place_market_buy_order(self, symbol: str, quantity: int) -> OrderResult:
        """下市價買單 (使用漲停價)"""
        if not self._logged_in:
            return OrderResult(success=False, message="未登入")

        try:
            from esun_trade.order import OrderObject
            from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action

            order = OrderObject(
                stock_no=symbol,
                buy_sell=Action.Buy,
                quantity=quantity,
                price=None,  # 市價單不需指定價格
                price_flag=PriceFlag.LimitUp,  # 漲停價買入
                ap_code=APCode.Common,
                bs_flag=BSFlag.ROD,
                trade=Trade.Cash
            )

            result = self.trade_sdk.place_order(order)
            order_no = result.get('ord_no')

            if order_no:
                logger.info(f"市價買單已送出: {symbol}, 數量: {quantity} 張")
                return OrderResult(success=True, order_no=order_no)
            else:
                return OrderResult(success=False, message=str(result))

        except Exception as e:
            logger.error(f"下市價買單失敗: {e}")
            return OrderResult(success=False, message=str(e))

    def place_market_sell_order(self, symbol: str, quantity: int) -> OrderResult:
        """下市價賣單 (使用跌停價)"""
        if not self._logged_in:
            return OrderResult(success=False, message="未登入")

        try:
            from esun_trade.order import OrderObject
            from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action

            order = OrderObject(
                stock_no=symbol,
                buy_sell=Action.Sell,
                quantity=quantity,
                price=None,  # 市價單不需指定價格
                price_flag=PriceFlag.LimitDown,  # 跌停價賣出
                ap_code=APCode.Common,
                bs_flag=BSFlag.ROD,
                trade=Trade.Cash
            )

            result = self.trade_sdk.place_order(order)
            order_no = result.get('ord_no')

            if order_no:
                logger.info(f"市價賣單已送出: {symbol}, 數量: {quantity} 張")
                return OrderResult(success=True, order_no=order_no)
            else:
                return OrderResult(success=False, message=str(result))

        except Exception as e:
            logger.error(f"下市價賣單失敗: {e}")
            return OrderResult(success=False, message=str(e))

    def get_position(self, symbol: str) -> Optional[Position]:
        """取得持倉"""
        if not self._logged_in:
            return None

        try:
            inventories = self.trade_sdk.get_inventories()
            for item in inventories:
                if item.get('stock_no') == symbol:
                    return Position(
                        symbol=symbol,
                        quantity=item.get('quantity', 0),
                        avg_price=item.get('avg_price', 0),
                        unrealized_pnl=item.get('unrealized_pnl', 0)
                    )
            return None

        except Exception as e:
            logger.error(f"取得持倉失敗: {e}")
            return None

    def get_order_status(self, order_no: str) -> Optional[OrderInfo]:
        """查詢訂單狀態"""
        if not self._logged_in:
            return None

        try:
            orders = self.trade_sdk.get_orders()
            for order in orders:
                if order.get('ord_no') == order_no:
                    status = order.get('status', '')
                    filled_qty = order.get('filled_qty', 0)
                    order_qty = order.get('quantity', 0)

                    if status == 'cancelled':
                        order_status = 'cancelled'
                    elif filled_qty >= order_qty:
                        order_status = 'filled'
                    elif filled_qty > 0:
                        order_status = 'partial'
                    else:
                        order_status = 'pending'

                    return OrderInfo(
                        order_no=order_no,
                        symbol=order.get('stock_no', ''),
                        side='buy' if order.get('buy_sell') == 'B' else 'sell',
                        price=order.get('price', 0),
                        quantity=order_qty,
                        filled_qty=filled_qty,
                        status=order_status
                    )
            return None

        except Exception as e:
            logger.error(f"查詢訂單失敗: {e}")
            return None

    def get_orders(self) -> List[OrderInfo]:
        """取得所有訂單"""
        if not self._logged_in:
            return []

        try:
            orders = self.trade_sdk.get_orders()
            result = []
            for order in orders:
                status = order.get('status', '')
                filled_qty = order.get('filled_qty', 0)
                order_qty = order.get('quantity', 0)

                if status == 'cancelled':
                    order_status = 'cancelled'
                elif filled_qty >= order_qty:
                    order_status = 'filled'
                elif filled_qty > 0:
                    order_status = 'partial'
                else:
                    order_status = 'pending'

                result.append(OrderInfo(
                    order_no=order.get('ord_no', ''),
                    symbol=order.get('stock_no', ''),
                    side='buy' if order.get('buy_sell') == 'B' else 'sell',
                    price=order.get('price', 0),
                    quantity=order_qty,
                    filled_qty=filled_qty,
                    status=order_status
                ))
            return result

        except Exception as e:
            logger.error(f"取得訂單列表失敗: {e}")
            return []

    @staticmethod
    def get_required_config_fields() -> List[Dict]:
        """取得需要的設定欄位"""
        return [
            {
                'name': 'config_file',
                'description': '設定檔路徑 (config.ini)',
                'type': 'text',
                'required': False
            },
            {
                'name': 'api_key',
                'description': 'API Key',
                'type': 'text',
                'required': True
            },
            {
                'name': 'api_secret',
                'description': 'API Secret',
                'type': 'password',
                'required': True
            },
            {
                'name': 'account',
                'description': '證券帳號',
                'type': 'text',
                'required': True
            },
            {
                'name': 'password',
                'description': '交易密碼',
                'type': 'password',
                'required': True
            },
            {
                'name': 'cert_path',
                'description': '憑證檔案路徑 (.p12)',
                'type': 'file',
                'required': True
            },
            {
                'name': 'cert_password',
                'description': '憑證密碼',
                'type': 'password',
                'required': True
            }
        ]

    @staticmethod
    def validate_config(config: Dict) -> tuple:
        """驗證設定是否完整"""
        # 如果有 config_file，檢查檔案存在
        if config.get('config_file'):
            if not Path(config['config_file']).exists():
                return False, f"設定檔不存在: {config['config_file']}"
            return True, ""

        # 否則檢查必要欄位
        required = ['api_key', 'api_secret', 'account', 'password', 'cert_path', 'cert_password']
        missing = [f for f in required if not config.get(f)]

        if missing:
            return False, f"缺少必要設定: {', '.join(missing)}"

        if not Path(config['cert_path']).exists():
            return False, f"憑證檔案不存在: {config['cert_path']}"

        return True, ""
