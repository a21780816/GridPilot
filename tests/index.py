from configparser import ConfigParser
from esun_trade.sdk import SDK

# 讀取設定檔
config = ConfigParser()
config.read('/Users/youchenghan/Projects/stock/config.simulation.ini')
# 將設定檔內容寫至 SDK 中，並確認是否已設定密碼
sdk = SDK(config)