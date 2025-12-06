"""
網格交易機器人配置
"""

# ============================================
# Telegram Bot 設定 (必填)
# ============================================

# Telegram Bot Token（從 @BotFather 取得）
# 步驟：
# 1. 在 Telegram 搜尋 @BotFather
# 2. 發送 /newbot 建立機器人
# 3. 複製 Bot Token 到這裡
TELEGRAM_BOT_TOKEN = "8549219693:AAF5px7S_6bkqO98ANlKHA166PrENUDMe0w"


# ============================================
# 系統設定
# ============================================

# 最大同時運行網格數
MAX_GRIDS = 50

# 用戶資料存放目錄
USERS_DIR = "./users"


# ============================================
# 以下為舊版單機模式設定 (可忽略)
# 新架構下，每個用戶的設定會透過 Telegram Bot 互動設定
# 並儲存在 users/{chat_id}/ 目錄下
# ============================================

# 富果交易 API 配置檔路徑 (舊版單機模式用)
CONFIG_FILE = "./config/config.simulation.ini"

# Telegram Chat ID (舊版單機模式用)
TELEGRAM_CHAT_ID = "723878405"
TELEGRAM_ENABLED = True
TELEGRAM_STATUS_INTERVAL = 3600

# 網格交易策略參數 (舊版單機模式用)
STOCK_SYMBOL = "2330"
LOWER_PRICE = 1500.0
UPPER_PRICE = 1520.0
GRID_NUM = 10
QUANTITY_PER_GRID = 1
CHECK_INTERVAL = 60

# 風險控制參數 (舊版單機模式用)
MAX_CAPITAL = 1000000
MAX_POSITION = None
STOP_LOSS_PRICE = None
TAKE_PROFIT_PRICE = None
