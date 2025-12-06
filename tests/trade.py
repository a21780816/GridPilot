"""
交易功能測試
"""
from configparser import ConfigParser
from esun_trade.sdk import SDK
from esun_trade.order import OrderObject
from esun_trade.constant import APCode, Trade, PriceFlag, BSFlag, Action

# 讀取設定檔（使用相對路徑）
config = ConfigParser()
config.read('./config/config.simulation.ini')
sdk = SDK(config)

# 登入
sdk.login()

# 建立委託物件（加入完整欄位）
order = OrderObject(
    stock_no="2884",
    buy_sell=Action.Buy,
    quantity=2,
    price=None,
    price_flag=PriceFlag.LimitDown,
    ap_code=APCode.Common,
    bs_flag=BSFlag.ROD,
    trade=Trade.Cash
)

result = sdk.place_order(order)
print(f"下單結果: {result}")
