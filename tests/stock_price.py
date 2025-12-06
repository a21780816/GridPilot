from esun_marketdata import EsunMarketdata
from configparser import ConfigParser
from esun_trade.sdk import SDK
 
# 讀取設定檔
config = ConfigParser()
config.read('./config.simulation.ini') # 以模擬環境進行演練
 
# 登入
sdk = SDK(config)
sdk.login()

# 須確認您是否有當沖權限 -> 可參考：reference/python#get_trade_status
user_day_trade_status = sdk.get_trade_status()['day_trade_code']
print(f"您的當沖權限狀態: {user_day_trade_status}")

realtime_sdk = EsunMarketdata(config)
realtime_sdk.login()

stock = realtime_sdk.rest_client.stock  # Stock REST API client
symbol = "2603"
# 須先確認該股票是否可以先買後賣
symbol_can_day_trade = stock.intraday.ticker(symbol=symbol)['canBuyDayTrade']
print(f"股票 {symbol} 可以當沖買賣: {symbol_can_day_trade}")