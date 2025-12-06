from configparser import ConfigParser
from esun_trade.sdk import SDK
 
# 讀取設定檔
config = ConfigParser()
config.read('./config.simulation.ini') # 以模擬環境進行演練
 
# 登入
sdk = SDK(config)
sdk.login()